# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CourseGroup(models.Model):
    _name = 'course.group'
    _description = 'Kurs Qrupu'
    _order = 'name'
    
    name = fields.Char(string="Qrup Adı", required=True)
    program_id = fields.Many2many('course.program', string="Program", required=True)
    course_id = fields.Many2many('course.course', string="Kurs", required=True)
    
    # Qrup qrafiki
    schedule_ids = fields.One2many('course.group.schedule', 'group_id', string="Qrup Qrafiki")
    number_of_weeks = fields.Integer(string="Həftə sayı", default=4)
    start_date = fields.Date(string="Başlama Tarixi", default=fields.Date.today, required=True)
    end_date = fields.Date(compute='_compute_end_date', string="Bitmə Tarixi")

    # Qrup üzvləri
    teacher_id = fields.Many2one('res.partner', string="Müəllim", domain=[('is_teacher', '=', True)])
    member_ids = fields.One2many('course.group.member', 'group_id', string="Qrup Üzvləri")
    member_count = fields.Integer(string="Üzv Sayı", compute='_compute_member_count')
    
    # Dərs günləri
    lesson_day_ids = fields.One2many('course.group.lesson.day', 'group_id', string="Dərs Günləri")
    
    # Statistika sahələri
    lesson_day_count = fields.Integer(
        string='Ümumi Dərs Sayı', compute='_compute_lesson_stats'
    )
    lessons_with_teacher_count = fields.Integer(
        string='Müəllimi olan Dərslər', compute='_compute_lesson_stats'
    )
    
    # Aktivlik
    is_active = fields.Boolean(string="Aktiv", default=True)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")

    @api.depends('number_of_weeks', 'start_date')
    def _compute_end_date(self):
        for group in self:
            if group.start_date:
                group.end_date = group.start_date + timedelta(weeks=group.number_of_weeks)
            else:
                group.end_date = False

    @api.depends('member_ids')
    def _compute_member_count(self):
        for group in self:
            group.member_count = len(group.member_ids.filtered(lambda m: m.status == 'active'))
    
    @api.depends('lesson_day_ids', 'lesson_day_ids.teacher_id')
    def _compute_lesson_stats(self):
        for group in self:
            group.lesson_day_count = len(group.lesson_day_ids)
            group.lessons_with_teacher_count = len(group.lesson_day_ids.filtered('teacher_id'))
    
    def generate_lesson_days(self):
        """Həftəlik qrafikə və həftə sayına əsasən dərs günlərini yaradır"""
        self.ensure_one()
        
        # Mövcud dərs günlərini sil
        self.lesson_day_ids.unlink()
        
        if not self.start_date or not self.number_of_weeks or not self.schedule_ids:
            return
        
        lesson_vals = []
        current_date = self.start_date
        end_date = self.end_date
        
        while current_date <= end_date:
            day_of_week = str(current_date.weekday())
            
            # Bu günə aid qrafik var mı?
            day_schedules = self.schedule_ids.filtered(
                lambda s: s.day_of_week == day_of_week and s.is_active
            )
            
            for schedule in day_schedules:
                lesson_vals.append({
                    'group_id': self.id,
                    'lesson_date': current_date,
                    'start_time': schedule.start_time,
                    'end_time': schedule.end_time,
                    'teacher_id': self.teacher_id.id if self.teacher_id else False,
                    'status': 'scheduled'
                })
            
            current_date += timedelta(days=1)
        
        if lesson_vals:
            self.env['course.group.lesson.day'].create(lesson_vals)
    
    @api.onchange('start_date', 'number_of_weeks', 'schedule_ids')
    def _onchange_schedule_data(self):
        """Qrafik dəyişdikdə dərs günlərini yenilə"""
        if self.start_date and self.number_of_weeks and self.schedule_ids:
            # Bu onchange-də dəyişiklik etmirik, sadəcə məlumat veririk
            pass
    
    def action_generate_lesson_days(self):
        """Dərs günlərini yaratmaq üçün button action"""
        self.generate_lesson_days()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Uğurlu',
                'message': 'Dərs günləri uğurla yaradıldı.',
                'type': 'success',
            }
        }
    
    def action_assign_all_teachers(self):
        """Bütün dərs günlərinə qrupun əsas müəllimini təyin et"""
        self.ensure_one()
        if not self.teacher_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Xəbərdarlıq',
                    'message': 'Əvvəlcə qrupun əsas müəllimini təyin edin.',
                    'type': 'warning',
                }
            }
        
        # Bütün dərs günlərinə təyin et
        lesson_days = self.lesson_day_ids.filtered(lambda l: not l.teacher_id)
        lesson_days.write({'teacher_id': self.teacher_id.id})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Uğurlu',
                'message': f'{len(lesson_days)} dərsdə müəllim təyin edildi.',
                'type': 'success',
            }
        }

class CourseGroupSchedule(models.Model):
    _name = 'course.group.schedule'
    _description = 'Kurs Qrup Qrafiki'
    _order = 'day_of_week, start_time'

    group_id = fields.Many2one('course.group', string="Qrup", required=True, ondelete='cascade')
    
    # Həftənin günü
    day_of_week = fields.Selection([
        ('0', 'Bazar ertəsi'),
        ('1', 'Çərşənbə axşamı'),
        ('2', 'Çərşənbə'),
        ('3', 'Cümə axşamı'),
        ('4', 'Cümə'),
        ('5', 'Şənbə'),
        ('6', 'Bazar')
    ], string="Həftənin Günü", required=True)
    
    # Vaxt aralığı
    start_time = fields.Float(string="Başlama Vaxtı", required=True, help="Məsələn 19.5 = 19:30")
    end_time = fields.Float(string="Bitmə Vaxtı", required=True, help="Məsələn 20.5 = 20:30")
    
    # Aktivlik
    is_active = fields.Boolean(string="Aktiv", default=True)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    @api.constrains('start_time', 'end_time')
    def _check_time_range(self):
        for schedule in self:
            if schedule.start_time >= schedule.end_time:
                raise ValidationError("Başlama vaxtı bitmə vaxtından kiçik olmalıdır!")
            if schedule.start_time < 0 or schedule.start_time > 24:
                raise ValidationError("Başlama vaxtı 0-24 aralığında olmalıdır!")
            if schedule.end_time < 0 or schedule.end_time > 24:
                raise ValidationError("Bitmə vaxtı 0-24 aralığında olmalıdır!")


class CourseGroupLessonDay(models.Model):
    _name = 'course.group.lesson.day'
    _description = 'Qrup Dərs Günləri'
    _order = 'lesson_date, start_time'
    
    group_id = fields.Many2one('course.group', string="Qrup", required=True, ondelete='cascade')
    lesson_date = fields.Date(string="Dərs Tarixi", required=True)
    day_of_week = fields.Selection([
        ('0', 'Bazar ertəsi'),
        ('1', 'Çərşənbə axşamı'),
        ('2', 'Çərşənbə'),
        ('3', 'Cümə axşamı'),
        ('4', 'Cümə'),
        ('5', 'Şənbə'),
        ('6', 'Bazar')
    ], string="Həftənin Günü", compute='_compute_day_of_week', store=True)
    
    start_time = fields.Float(string="Başlama Vaxtı")
    end_time = fields.Float(string="Bitmə Vaxtı")
    
    # Müəllim
    teacher_id = fields.Many2one('res.partner', string="Müəllim", domain=[('is_teacher', '=', True)])
    
    # Status
    status = fields.Selection([
        ('scheduled', 'Planlaşdırılıb'),
        ('completed', 'Keçirilib'),
        ('cancelled', 'Ləğv edilib')
    ], string="Status", default='scheduled')
    
    notes = fields.Text(string="Qeydlər")
    
    @api.depends('lesson_date')
    def _compute_day_of_week(self):
        for lesson in self:
            if lesson.lesson_date:
                lesson.day_of_week = str(lesson.lesson_date.weekday())
    
    @api.onchange('group_id')
    def _onchange_group_id(self):
        """Qrup seçildikdə default müəllimi təyin et"""
        if self.group_id and self.group_id.teacher_id:
            self.teacher_id = self.group_id.teacher_id
