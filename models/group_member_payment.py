# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GroupMemberPayment(models.Model):
    _name = 'group.member.payment'
    _description = 'Qrup Üzvü Ödənişi'
    _rec_name = 'display_name'
    _order = 'payment_date desc'

    # Əsas əlaqələr
    member_id = fields.Many2one('course.group.member', string='Qrup Üzvü', required=True, ondelete='cascade')
    student_name = fields.Char(string='Tələbə Adı', related='member_id.student_name.display_name', store=True, readonly=True)
    group_name = fields.Char(string='Qrup Adı', related='member_id.group_id.name', store=True, readonly=True)
    
    # Üzv ödəniş məlumatları
    member_total_amount = fields.Float(string='Ümumi Məbləğ', related='member_id.total_amount', readonly=True)
    member_paid_amount = fields.Float(string='Ödənilmiş', related='member_id.paid_amount', readonly=True)
    member_remaining_amount = fields.Float(string='Qalıq', related='member_id.remaining_amount', readonly=True)
    
    # Ödəniş məlumatları
    payment_date = fields.Date(string='Ödəniş Tarixi', default=fields.Date.today, required=True)
    amount = fields.Float(string='Məbləğ', required=True)

    # Ödəniş tipi
    payment_type = fields.Selection([
        ('initial', 'İlkin Ödəniş'),
        ('installment', 'Taksit'),
        ('remainder', 'Qalıq'),
        ('full', 'Tam Ödəniş'),
        ('additional', 'Əlavə Ödəniş')
    ], string='Ödəniş Tipi', default='full', required=True)
    
    # Ödəniş üsulu
    payment_method = fields.Selection([
        ('cash', 'Nəğd'),
        ('bank_transfer', 'Bank köçürməsi'),
        ('card', 'Kart'),
        ('online', 'Online'),
        ('other', 'Digər')
    ], string='Ödəniş Üsulu', default='cash')
    
    # Status
    is_confirmed = fields.Boolean(string='Təsdiqləndi', default=True)
    
    # Qeydlər
    notes = fields.Text(string='Qeydlər')
    
    # Computed fields
    display_name = fields.Char(string='Ad', compute='_compute_display_name', store=True)
    
    @api.depends('student_name', 'amount', 'payment_date')
    def _compute_display_name(self):
        for payment in self:
            if payment.student_name and payment.amount:
                payment.display_name = f"{payment.student_name} - {payment.amount} AZN ({payment.payment_date})"
            else:
                payment.display_name = "Yeni Ödəniş"
    
    @api.constrains('amount')
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError("Ödəniş məbləği müsbət olmalıdır!")
    
    @api.model
    def create(self, vals):
        """Ödəniş yaradıldıqda üzvün ödəniş məlumatlarını yenilə"""
        payment = super().create(vals)
        payment.member_id._update_payment_status()
        return payment
    
    def write(self, vals):
        """Ödəniş yenilənəndə üzvün ödəniş məlumatlarını yenilə"""
        res = super().write(vals)
        for payment in self:
            payment.member_id._update_payment_status()
        return res
    
    def unlink(self):
        """Ödəniş silinəndə üzvün ödəniş məlumatlarını yenilə"""
        members = self.mapped('member_id')
        res = super().unlink()
        for member in members:
            member._update_payment_status()
        return res