# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class TeacherSalary(models.Model):
    _name = 'teacher.salary'
    _description = 'Müəllim Əmək Haqqı'
    _rec_name = 'display_name'
    _order = 'salary_month desc, teacher_id'

    # Əsas məlumatlar
    teacher_id = fields.Many2one('res.partner', string='Müəllim', required=True, 
                                domain=[('is_teacher', '=', True)], ondelete='cascade')
    salary_month = fields.Date(string='Maaş Ayı', required=True, default=fields.Date.today)
    salary_type = fields.Selection(related='teacher_id.salary_type', string='Maaş Tipi', readonly=True)
    
    # Sabit maaş məlumatları
    fixed_salary = fields.Float(related='teacher_id.fixed_salary', string='Sabit Maaş', readonly=True)
    
    # Faizli maaş məlumatları
    lesson_rate = fields.Float(related='teacher_id.lesson_rate', string='Dərs Faizi', readonly=True)
    lesson_count = fields.Integer(string='Dərs Sayı', compute='_compute_lesson_count', store=True)
    calculated_salary = fields.Float(string='Hesablanmış Maaş', compute='_compute_calculated_salary', store=True)
    
    # Əlavə məlumatlar
    bonus = fields.Float(string='Bonus', default=0.0)
    deduction = fields.Float(string='Tutulan Məbləğ', default=0.0)
    final_salary = fields.Float(string='Son Maaş', compute='_compute_final_salary', store=True)
    
    # Status və qeydlər
    status = fields.Selection([
        ('draft', 'Qaralama'),
        ('confirmed', 'Təsdiqləndi'),
        ('paid', 'Ödənildi')
    ], string='Status', default='draft', required=True)
    
    notes = fields.Text(string='Qeydlər')
    display_name = fields.Char(string='Ad', compute='_compute_display_name', store=True)

    @api.depends('teacher_id', 'salary_month')
    def _compute_display_name(self):
        for salary in self:
            if salary.teacher_id and salary.salary_month:
                month_year = salary.salary_month.strftime('%m/%Y')
                salary.display_name = f"{salary.teacher_id.name} - {month_year}"
            else:
                salary.display_name = "Yeni Maaş"

    @api.depends('teacher_id', 'salary_month')
    def _compute_lesson_count(self):
        for salary in self:
            if salary.teacher_id and salary.salary_month:
                # Həmin ayda müəllimin keçdiyi dərsləri say
                start_date = salary.salary_month.replace(day=1)
                if salary.salary_month.month == 12:
                    end_date = salary.salary_month.replace(year=salary.salary_month.year + 1, month=1, day=1)
                else:
                    end_date = salary.salary_month.replace(month=salary.salary_month.month + 1, day=1)
                
                lesson_days = self.env['course.group.lesson.day'].search([
                    ('teacher_id', '=', salary.teacher_id.id),
                    ('lesson_date', '>=', start_date),
                    ('lesson_date', '<', end_date),
                    ('status', '=', 'completed')
                ])
                salary.lesson_count = len(lesson_days)
            else:
                salary.lesson_count = 0

    @api.depends('salary_type', 'fixed_salary', 'lesson_rate', 'lesson_count')
    def _compute_calculated_salary(self):
        for salary in self:
            if salary.salary_type == 'fixed':
                salary.calculated_salary = salary.fixed_salary
            elif salary.salary_type == 'percentage':
                salary.calculated_salary = salary.lesson_count * salary.lesson_rate
            else:
                salary.calculated_salary = 0.0

    @api.depends('calculated_salary', 'bonus', 'deduction')
    def _compute_final_salary(self):
        for salary in self:
            salary.final_salary = salary.calculated_salary + salary.bonus - salary.deduction

    @api.constrains('teacher_id', 'salary_month')
    def _check_unique_month(self):
        """Bir müəllim üçün eyni ayda yalnız bir maaş qeydi ola bilər"""
        for salary in self:
            existing = self.search([
                ('teacher_id', '=', salary.teacher_id.id),
                ('salary_month', '=', salary.salary_month),
                ('id', '!=', salary.id)
            ])
            if existing:
                month_year = salary.salary_month.strftime('%m/%Y')
                raise ValidationError(
                    f"{salary.teacher_id.name} üçün {month_year} ayında artıq maaş qeydi mövcuddur!"
                )

    def action_confirm(self):
        """Maaşı təsdiqlə"""
        self.write({'status': 'confirmed'})

    def action_mark_paid(self):
        """Maaşı ödənilmiş olaraq qeyd et"""
        self.write({'status': 'paid'})

    def action_reset_to_draft(self):
        """Qaralama statusuna qaytar"""
        self.write({'status': 'draft'})

    @api.model
    def generate_monthly_salaries(self, month_date=None):
        """Bütün müəllimlər üçün aylıq maaş qeydləri yarat"""
        if not month_date:
            month_date = fields.Date.today()
        
        teachers = self.env['res.partner'].search([('is_teacher', '=', True)])
        created_salaries = []
        
        for teacher in teachers:
            # Yoxla ki, bu ay üçün artıq maaş qeydi varmı
            existing = self.search([
                ('teacher_id', '=', teacher.id),
                ('salary_month', '=', month_date)
            ])
            
            if not existing:
                salary = self.create({
                    'teacher_id': teacher.id,
                    'salary_month': month_date,
                })
                created_salaries.append(salary)
        
        return created_salaries