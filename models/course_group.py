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
    
    # Üzv statistikaları
    total_monthly_payment = fields.Float(
        string='Ümumi Ödəniş', compute='_compute_member_stats'
    )
    active_member_count = fields.Integer(
        string='Aktiv Üzv Sayı', compute='_compute_member_stats'
    )
    
    # Aktivlik
    is_active = fields.Boolean(string="Aktiv", default=True)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")

    @api.depends('lesson_day_ids', 'lesson_day_ids.lesson_date')
    def _compute_end_date(self):
        for group in self:
            if group.lesson_day_ids:
                # Son dərs tarixini tap
                last_lesson_date = max(group.lesson_day_ids.mapped('lesson_date'))
                group.end_date = last_lesson_date
            elif group.start_date and group.number_of_weeks:
                # Əgər dərs günləri yoxdursa, həftə sayına görə hesabla
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
    
    @api.depends('member_ids', 'member_ids.status', 'member_ids.monthly_payment')
    def _compute_member_stats(self):
        for group in self:
            active_members = group.member_ids.filtered(lambda m: m.status == 'active')
            group.active_member_count = len(active_members)
            group.total_monthly_payment = sum(active_members.mapped('monthly_payment'))
    
    def generate_lesson_days(self):
        """Həftəlik qrafikə və həftə sayına əsasən dərs günlərini yaradır"""
        self.ensure_one()
        
        # Köhnə sistemi qoru amma sadələşdir
        # Yalnız "scheduled" statusu olan köhnə dərsləri sil
        old_scheduled_lessons = self.lesson_day_ids.filtered(lambda l: l.status == 'scheduled')
        old_scheduled_lessons.unlink()
        
        if not self.start_date or not self.number_of_weeks or not self.schedule_ids:
            return
        
        lesson_vals = []
        current_date = self.start_date
        planned_end_date = self.start_date + timedelta(weeks=self.number_of_weeks)
        
        while current_date <= planned_end_date:
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
        
        # Yeni dərs günləri yarat
        if lesson_vals:
            new_lessons = self.env['course.group.lesson.day'].create(lesson_vals)
            
            # Yeni yaradılan dərs günləri üçün avtomatik devamiyyət yarat
            self._create_attendance_for_new_lessons(new_lessons)
    
    def _create_attendance_for_new_lessons(self, lesson_days):
        """Yeni yaradılmış dərs günləri üçün aktiv üzvlərə devamiyyət yarat"""
        self.ensure_one()
        
        active_members = self.member_ids.filtered(lambda m: m.status == 'active')
        attendance_vals = []
        
        for lesson_day in lesson_days:
            for member in active_members:
                # Yalnız üzvün başlama tarixindən sonrakı dərslər
                if lesson_day.lesson_date >= member.join_date:
                    # End date varsa və ötübse devamiyyət yaratma
                    if member.end_date and lesson_day.lesson_date > member.end_date:
                        continue
                        
                    attendance_vals.append({
                        'lesson_day_id': lesson_day.id,
                        'student_id': member.id,
                        'is_present': True
                    })
        
        if attendance_vals:
            self.env['course.lesson.attendance'].create(attendance_vals)
    
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
                'message': 'Dərs günləri yeniləndi. Mövcud statuslar və devamiyyət qorundu.',
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
    _rec_name = 'display_name'
    
    group_id = fields.Many2one('course.group', string="Qrup", required=True, ondelete='cascade')
    lesson_date = fields.Date(string="Dərs Tarixi", required=True)
    display_name = fields.Char(string='Ad', compute='_compute_display_name', store=True)
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
    
    # Calendar view üçün datetime sahələri
    datetime_start = fields.Datetime(string="Başlama Datetime", compute='_compute_datetime_fields', store=True)
    datetime_end = fields.Datetime(string="Bitmə Datetime", compute='_compute_datetime_fields', store=True)
    
    # Müəllim
    teacher_id = fields.Many2one('res.partner', string="Müəllim", domain=[('is_teacher', '=', True)])
    
    # Status
    status = fields.Selection([
        ('scheduled', 'Planlaşdırılıb'),
        ('completed', 'Keçirilib'),
        ('cancelled', 'Ləğv edilib')
    ], string="Status", default='scheduled')
    
    notes = fields.Text(string="Qeydlər")
    
    # Devamiyyət əlaqəsi
    attendance_list = fields.One2many('course.lesson.attendance', 'lesson_day_id', string="İştirak Siyahısı")
    
    @api.depends('lesson_date')
    def _compute_day_of_week(self):
        for lesson in self:
            if lesson.lesson_date:
                lesson.day_of_week = str(lesson.lesson_date.weekday())
    
    @api.depends('lesson_date', 'start_time', 'end_time')
    def _compute_datetime_fields(self):
        for lesson in self:
            if lesson.lesson_date and lesson.start_time is not False:
                # Float time-ı saat və dəqiqəyə çevir
                hours = int(lesson.start_time)
                minutes = int((lesson.start_time % 1) * 60)
                
                # Date və time-ı birləşdirərək datetime yarat
                from datetime import datetime, time
                lesson.datetime_start = datetime.combine(
                    lesson.lesson_date, 
                    time(hours, minutes)
                )
                
                if lesson.end_time is not False:
                    end_hours = int(lesson.end_time)
                    end_minutes = int((lesson.end_time % 1) * 60)
                    lesson.datetime_end = datetime.combine(
                        lesson.lesson_date,
                        time(end_hours, end_minutes)
                    )
                else:
                    # Əgər bitmə vaxtı yoxdursa, 1 saat əlavə et
                    lesson.datetime_end = lesson.datetime_start + timedelta(hours=1)
            else:
                lesson.datetime_start = False
                lesson.datetime_end = False
    
    @api.depends('group_id', 'start_time', 'end_time', 'status')
    def _compute_display_name(self):
        for lesson in self:
            if lesson.group_id:
                # Saatları format et
                start = f"{int(lesson.start_time):02d}:{int((lesson.start_time % 1) * 60):02d}" if lesson.start_time else ""
                end = f"{int(lesson.end_time):02d}:{int((lesson.end_time % 1) * 60):02d}" if lesson.end_time else ""
                time_range = f"({start}-{end})" if start and end else ""
                
                # Status tərcüməsi
                status_dict = {
                    'scheduled': 'Planlaşdırılıb',
                    'completed': 'Keçirilib', 
                    'cancelled': 'Ləğv edilib'
                }
                status_text = status_dict.get(lesson.status, lesson.status or '')
                
                # Format: "Qrup adı (saat) - Status"
                lesson.display_name = f"{lesson.group_id.name} {time_range} - {status_text}"
            else:
                lesson.display_name = "Yeni Dərs"
    
    @api.onchange('group_id')
    def _onchange_group_id(self):
        """Qrup seçildikdə default müəllimi təyin et"""
        if self.group_id and self.group_id.teacher_id:
            self.teacher_id = self.group_id.teacher_id
    
    @api.model
    def create(self, vals):
        """Dərs günü yaradılanda avtomatik olaraq devamiyyət qeydlərini yarat"""
        lesson_day = super().create(vals)
        lesson_day._create_attendance_records()
        return lesson_day
    
    def _create_attendance_records(self):
        """Bu dərs günü üçün qrup üzvlərinin devamiyyət qeydlərini yarat"""
        self.ensure_one()
        if not self.group_id:
            return
            
        # Aktiv qrup üzvlərini tap
        active_members = self.group_id.member_ids.filtered(lambda m: m.status == 'active')
        
        # Hər üzv üçün devamiyyət qeydi yarat (yalnız qrupə başlama tarixindən sonra)
        attendance_vals = []
        for member in active_members:
            # Yalnız üzvün qrupa başlama tarixi dərs tarixindən əvvəl və ya bərabərdirsə əlavə et
            if member.join_date <= self.lesson_date:
                # Əvvəlcə bu üzvün bu dərs günü üçün qeydi var mı yoxla
                existing = self.env['course.lesson.attendance'].search([
                    ('lesson_day_id', '=', self.id),
                    ('student_id', '=', member.id)
                ])
                if not existing:
                    attendance_vals.append({
                        'lesson_day_id': self.id,
                        'student_id': member.id,
                        'is_present': True  # Default olaraq iştirak var
                    })
        
        if attendance_vals:
            self.env['course.lesson.attendance'].create(attendance_vals)
    
    def action_refresh_attendance(self):
        """Yeni üzvlər əlavə olunduqda devamiyyət qeydlərini yenilə"""
        self.ensure_one()
        self._create_attendance_records()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Uğurlu',
                'message': 'Devamiyyət qeydləri yeniləndi.',
                'type': 'success',
            }
        }
