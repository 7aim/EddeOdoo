from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CourseGroupMember(models.Model):
    _name = 'course.group.member'
    _description = 'Qrup Üzvlüyü'
    _rec_name = 'student_name'
    _order = 'join_date desc'

    # Əsas məlumatlar
    student_name = fields.Many2one('edde.course.registration', string='Tələbə', required=True, 
                                   domain=[('status', 'in', ['confirmed', 'in_progress'])])
    group_id = fields.Many2one('course.group', string='Qrup', required=True)
    
    # Tariх və ödəniş
    join_date = fields.Date(string='Başlama Tarixi', default=fields.Date.today, required=True)
    monthly_payment = fields.Float(string='Ödəniş', help='Bu qrup üçün ödəniş məbləği')
    
    # Status
    status = fields.Selection([
        ('active', 'Aktiv'),
        ('inactive', 'Qeyri-aktiv'),
        ('completed', 'Tamamlandı'),
        ('suspended', 'Dayandırıldı')
    ], string='Status', default='active')
    
    # Hesablanmış sahələr
    student_id = fields.Many2one(related='student_name', string='Tələbə ID', store=True, readonly=True)
    display_name = fields.Char(string='Ad', compute='_compute_display_name', store=True)
    
    # Qeydlər
    notes = fields.Text(string='Qeydlər')
    
    @api.depends('student_name', 'group_id')
    def _compute_display_name(self):
        for member in self:
            if member.student_name and member.group_id:
                member.display_name = f"{member.student_name.student_code} - {member.group_id.name}"
            else:
                member.display_name = "Yeni üzv"
    
    @api.constrains('student_name', 'group_id', 'status')
    def _check_unique_active_membership(self):
        """Bir tələbə eyni qrupda yalnız bir aktiv üzvlüyə malik ola bilər"""
        for member in self:
            if member.status == 'active':
                existing = self.search([
                    ('student_name', '=', member.student_name.id),
                    ('group_id', '=', member.group_id.id),
                    ('status', '=', 'active'),
                    ('id', '!=', member.id)
                ])
                if existing:
                    raise ValidationError(
                        f"{member.student_name.student_code} artıq {member.group_id.name} qrupunda aktiv üzvdür!"
                    )
    
    @api.model
    def create(self, vals):
        """Üzvlük yaradıldıqda tələbənin ödənişini yenilə"""
        member = super().create(vals)
        if member.monthly_payment and member.student_name:
            member.student_name.write({'monthly_payment': member.monthly_payment})
        return member
    
    def write(self, vals):
        """Üzvlük yenilənəndə tələbənin ödənişini yenilə"""
        res = super().write(vals)
        if 'monthly_payment' in vals:
            for member in self:
                if member.student_name and member.status == 'active':
                    member.student_name.write({'monthly_payment': member.monthly_payment})
        return res