# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CourseLessonAttendance(models.Model):
    _name = 'course.lesson.attendance'
    _description = 'Dərs İştirakı'
    _rec_name = 'display_name'

    lesson_day_id = fields.Many2one(
        'course.group.lesson.day', 
        string='Dərs Günü', 
        required=True, 
        ondelete='cascade'
    )
    student_id = fields.Many2one(
        'course.group.member', 
        string='Tələbə', 
        required=True,
        ondelete='cascade'
    )
    student_name = fields.Char(string='Tələbə Adı', related='student_id.student_name.display_name', store=True, readonly=True)
    lesson_date = fields.Date(string='Dərs Tarixi', related='lesson_day_id.lesson_date', store=True, readonly=True)
    group_id = fields.Many2one('course.group', string='Qrup', related='lesson_day_id.group_id', store=True, readonly=True)
    lesson_status = fields.Selection(string='Dərs Statusu', related='lesson_day_id.status', store=True, readonly=True)
    is_present = fields.Boolean(string='İştirak', default=True)
    attendance_status = fields.Char(string='İştirak Statusu', compute='_compute_attendance_status', store=True)
    present_count = fields.Integer(string='İştirak Sayı', compute='_compute_attendance_counts', store=True)
    absent_count = fields.Integer(string='Qeyb Sayı', compute='_compute_attendance_counts', store=True)
    excuse = fields.Char(string='Bəhanə')
    notes = fields.Text(string='Qeydlər')
    
    # Computed fields
    display_name = fields.Char(string='Ad', compute='_compute_display_name', store=True)

    @api.depends('is_present')
    def _compute_attendance_status(self):
        for record in self:
            record.attendance_status = "Yes" if record.is_present else "No"
    
    @api.depends('is_present')
    def _compute_attendance_counts(self):
        for record in self:
            if record.is_present:
                record.present_count = 1
                record.absent_count = 0
            else:
                record.present_count = 0
                record.absent_count = 1

    @api.depends('student_id', 'lesson_day_id', 'is_present')
    def _compute_display_name(self):
        for record in self:
            if record.student_id and record.lesson_day_id:
                status = "✓" if record.is_present else "✗"
                record.display_name = f"{record.student_name} - {record.lesson_day_id.lesson_date} [{status}]"
            else:
                record.display_name = "Yeni İştirak Qeydi"

    @api.constrains('lesson_day_id', 'student_id')
    def _check_unique_attendance(self):
        # Yalnız create zamanı check et, update zamanı yox
        for record in self:
            if not record.id:  # Yeni qeyd yaradılırsa
                existing = self.search([
                    ('lesson_day_id', '=', record.lesson_day_id.id),
                    ('student_id', '=', record.student_id.id)
                ])
                if existing:
                    raise ValidationError(
                        f"Bu tələbənin ({record.student_name}) "
                        f"bu dərs günü üçün ({record.lesson_day_id.lesson_date}) "
                        f"artıq devamiyyət qeydi var!"
                    )