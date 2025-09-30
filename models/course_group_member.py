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
    end_date = fields.Date(string='Bitmə Tarixi', help='Bu üzvün qrupdan çıxma tarixi')
    monthly_payment = fields.Float(string='Ödəniş', help='Bu qrup üçün ödəniş məbləği')
    
    # Ödəniş sistemi
    payment_plan = fields.Selection([
        ('full', 'Tam Ödəniş'),
        ('partial', 'İlkin + Qalıq'),
        ('installment', 'Taksit'),
        ('custom', 'Fərdi Plan')
    ], string='Ödəniş Planı', default='full')
    
    total_amount = fields.Float(string='Ümumi Məbləğ', help='Bu üzv üçün ümumi ödəniş məbləği')
    paid_amount = fields.Float(string='Ödənilmiş Məbləğ', compute='_compute_payment_status', store=True)
    remaining_amount = fields.Float(string='Qalan Məbləğ', compute='_compute_payment_status', store=True)
    
    payment_status = fields.Selection([
        ('pending', 'Gözləmədə'),
        ('partial', 'Qismən Ödənilmiş'),
        ('paid', 'Tam Ödənilmiş'),
        ('overpaid', 'Artıq Ödənilmiş')
    ], string='Ödəniş Vəziyyəti', compute='_compute_payment_status', store=True)
    
    # Ödəniş qeydləri
    payment_ids = fields.One2many('group.member.payment', 'member_id', string='Ödəniş Qeydləri')
    
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
        """Üzvlük yaradıldıqda tələbənin ödənişini yenilə və devamiyyət qeydləri yarat"""
        member = super().create(vals)
        
        # Ödənişi yenilə
        if member.monthly_payment and member.student_name:
            member.student_name.write({'monthly_payment': member.monthly_payment})
        
        # Mövcud dərs günləri üçün avtomatik devamiyyət qeydləri yarat
        if member.status == 'active':
            member._create_attendance_for_existing_lessons()
        
        return member
    
    def _create_attendance_for_existing_lessons(self):
        """Bu üzv üçün mövcud dərs günlərinə devamiyyət qeydləri yarat"""
        self.ensure_one()
        
        # Yalnız bu üzvün başlama tarixindən sonrakı dərs günləri
        lesson_days = self.group_id.lesson_day_ids.filtered(
            lambda l: l.lesson_date >= self.join_date
        )
        
        attendance_vals = []
        for lesson_day in lesson_days:
            # Bu dərs günü üçün artıq qeydi var mı?
            existing = self.env['course.lesson.attendance'].search([
                ('lesson_day_id', '=', lesson_day.id),
                ('student_id', '=', self.id)
            ])
            
            if not existing:
                attendance_vals.append({
                    'lesson_day_id': lesson_day.id,
                    'student_id': self.id,
                    'is_present': True  # Default olaraq iştirak var
                })
        
        if attendance_vals:
            self.env['course.lesson.attendance'].create(attendance_vals)
    
    def write(self, vals):
        """Üzvlük yenilənəndə tələbənin ödənişini yenilə və devamiyyət idarə et"""
        res = super().write(vals)
        
        # Ödənişi yenilə
        if 'monthly_payment' in vals:
            for member in self:
                if member.student_name and member.status == 'active':
                    member.student_name.write({'monthly_payment': member.monthly_payment})
        
        # Status dəyişdikdə devamiyyət idarə et
        if 'status' in vals:
            for member in self:
                if vals['status'] == 'active':
                    # Aktiv olduqda devamiyyət yarat
                    member._create_attendance_for_existing_lessons()
                else:
                    # Qeyri-aktiv olduqda gələcək dərslər üçün devamiyyət sil
                    member._remove_future_attendance()
        
        return res
    
    def _remove_future_attendance(self):
        """Gələcək dərslər üçün bu üzvün devamiyyət qeydlərini sil"""
        self.ensure_one()
        
        future_lessons = self.group_id.lesson_day_ids.filtered(
            lambda l: l.lesson_date >= fields.Date.today() and l.status == 'scheduled'
        )
        
        # Gələcək dərslər üçün devamiyyət qeydlərini sil
        attendances_to_remove = self.env['course.lesson.attendance'].search([
            ('lesson_day_id', 'in', future_lessons.ids),
            ('student_id', '=', self.id)
        ])
        
        if attendances_to_remove:
            attendances_to_remove.unlink()
    
    @api.depends('payment_ids', 'payment_ids.amount', 'payment_ids.is_confirmed', 'total_amount')
    def _compute_payment_status(self):
        for member in self:
            # Təsdiqlənmiş ödənişlərin cəmini hesabla
            confirmed_payments = member.payment_ids.filtered('is_confirmed')
            member.paid_amount = sum(confirmed_payments.mapped('amount'))
            
            # Qalan məbləği hesabla
            member.remaining_amount = member.total_amount - member.paid_amount
            
            # Ödəniş statusunu təyin et
            if member.total_amount <= 0:
                member.payment_status = 'pending'
            elif member.paid_amount <= 0:
                member.payment_status = 'pending'
            elif member.paid_amount >= member.total_amount:
                if member.paid_amount > member.total_amount:
                    member.payment_status = 'overpaid'
                else:
                    member.payment_status = 'paid'
            else:
                member.payment_status = 'partial'
    
    def _update_payment_status(self):
        """Ödəniş statusunu yenilə - payment model tərəfindən çağırılır"""
        self._compute_payment_status()
    
    def action_add_payment(self):
        """Yeni ödəniş əlavə etmək üçün wizard açar"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ödəniş Əlavə Et',
            'res_model': 'group.member.payment',
            'view_mode': 'form',
            'context': {
                'default_member_id': self.id,
                'default_payment_type': 'installment' if self.payment_plan == 'installment' else 'full'
            },
            'target': 'new'
        }
    
    def action_view_payments(self):
        """Bu üzvün bütün ödənişlərini göstər"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.student_name.display_name} - Ödənişlər',
            'res_model': 'group.member.payment',
            'view_mode': 'list,form',
            'domain': [('member_id', '=', self.id)],
            'context': {'default_member_id': self.id}
        }