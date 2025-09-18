from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class CourseRegistration(models.Model):
    _name = 'edde.course.registration'
    _description = 'Course Registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    student_code = fields.Char('Tələbə ID', readonly=True, copy=False, default='/')
    student_id = fields.Many2one('res.partner', string='Tələbə', required=True)
    father_name = fields.Char('Ata adı')
    id_card_number = fields.Char('Vəsiqə seriya nömrəsi')
    group_id = fields.Many2one('course.group', string="Qrup")
    schedule_ids = fields.One2many('course.lesson.schedule', 'lesson_id', string="Həftəlik Qrafik")

    attendance_ids = fields.One2many('course.lesson.attendance', 'lesson_id', string="Dərsə İştiraklar")
    total_attendances = fields.Integer(string="Ümumi İştirak", compute='_compute_total_attendances')

    # Program and Source
    program = fields.Many2one('course.program', string='Program')
    university = fields.Many2one('res.partner', string='Universitet')
    country = fields.Many2one('course.country', string='Ölkə')
    course = fields.Many2one('course.course', string='Kurs')
    source = fields.Many2one('course.source', string='Mənbə')
    
    # Additional Details
    purpose = fields.Text('Məqsəd')
    rejection_reason = fields.Text('İmtina səbəbi')
    note = fields.Text('Qeyd')
    
    # Status and Dates
    status = fields.Selection([
        ('draft', 'Qaralama'),
        ('pending', 'Gözləmədə'),
        ('confirmed', 'Təsdiqləndi'),
        ('in_progress', 'Davam edir'),
        ('completed', 'Tamamlandı'),
        ('cancelled', 'Ləğv edildi')
    ], string='Status', default='draft', tracking=True)
    create_date = fields.Datetime('Yaradılma tarixi', default=fields.Datetime.now, readonly=True)
    start_date = fields.Date('Başlama tarixi')
    
    # Contact Information
    email = fields.Char('Email')
    birth_date = fields.Date('Doğum tarixi')
    gender = fields.Selection([
        ('male', 'Kişi'),
        ('female', 'Qadın'),
        ('other', 'Digər')
    ], string='Cinsi')
    phone = fields.Char('Telefon')
    phone2 = fields.Char('Telefon 2')

    @api.depends('attendance_ids')
    def _compute_total_attendances(self):
        for lesson in self:
            lesson.total_attendances = len(lesson.attendance_ids)

    @api.onchange('group_id')
    def _onchange_group_id(self):
        """Qrup seçildikdə avtomatik qrafik əlavə et"""
        if self.group_id:
            # Əvvəlki qrafiki sil
            self.schedule_ids = [(5, 0, 0)]
            
            # Qrupun qrafikini kopyala
            schedule_vals = []
            for group_schedule in self.group_id.schedule_ids:
                if group_schedule.is_active:
                    schedule_vals.append((0, 0, {
                        'day_of_week': group_schedule.day_of_week,
                        'start_time': group_schedule.start_time,
                        'end_time': group_schedule.end_time,
                        'is_active': True,
                        'notes': f"Qrup qrafiki: {self.group_id.name}"
                    }))
            
            if schedule_vals:
                self.schedule_ids = schedule_vals

    @api.onchange('student_id')
    def _onchange_student_id(self):
        if self.student_id:
            self.email = self.student_id.email
            self.phone = self.student_id.phone
            self.program = self.student_id.program_id
            self.university = self.student_id.university_id
            self.country = self.student_id.student_country_id
            self.course = self.student_id.course_id
            self.source = self.student_id.source_id
    
    @api.model
    def create(self, vals):
        if 'student_code' not in vals or vals['student_code'] == '/':
            vals['student_code'] = self.env['ir.sequence'].next_by_code('edde.course.registration') or 'STU/'
        
        record = super(CourseRegistration, self).create(vals)
        record._check_and_set_start_date()
        return record

    def write(self, vals):
        res = super(CourseRegistration, self).write(vals)
        if 'status' in vals:
            self._check_and_set_start_date()
        return res

    def _check_and_set_start_date(self): 
        for rec in self:
            if rec.status == 'confirmed' and not rec.start_date:
                rec.start_date = fields.Date.today()

class CourseLessonSchedule(models.Model):
    _name = 'course.lesson.schedule'
    _description = 'Həftəlik Dərs Qrafiki (Sadə)'
    _order = 'day_of_week, start_time'

    lesson_id = fields.Many2one('edde.course.registration', string="Dərs", required=True, ondelete='cascade')
    student_id = fields.Many2one(related='lesson_id.student_id', string="Müştəri", store=True)
    
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
            

class CourseLessonAttendance(models.Model):
    _name = 'course.lesson.attendance'
    _description = 'Kurs Dərs İştirakı'
    _order = 'attendance_date desc, attendance_time desc'

    lesson_id = fields.Many2one('edde.course.registration', string="Dərs Abunəliyi", required=True)
    schedule_id = fields.Many2one('course.lesson.schedule', string="Dərs Qrafiki", required=True)
    student_id = fields.Many2one(related='lesson_id.student_id', string="Müştəri", store=True)
    
    # İştirak məlumatları
    attendance_date = fields.Date(string="İştirak Tarixi", default=fields.Date.today)
    attendance_time = fields.Datetime(string="İştirak Vaxtı", default=fields.Datetime.now)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")