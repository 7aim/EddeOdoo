from odoo import models, fields, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'
    
    def action_create_student_from_lead(self):
        """
        Lead-dən tələbə qeydiyyatı yaradır
        """
        self.ensure_one()
        
        # Əvvəlcə partner yarat (əgər yoxdursa)
        if not self.partner_id:
            partner_vals = {
                'name': self.contact_name or self.name,
                'email': self.email_from,
                'phone': self.phone,
                'mobile': self.mobile,
            }
            partner = self.env['res.partner'].create(partner_vals)
            self.write({'partner_id': partner.id})
        
        # İndi həmin partner üçün tələbə qeydiyyatı yarat
        vals = {
            'student_id': self.partner_id.id,
            'phone': self.partner_id.phone,
            'phone2': self.partner_id.mobile,
            'email': self.partner_id.email,
            'note': f"Lead-dən yaradılıb: {self.name}\n" + (self.description or ''),
        }
        
        # Tələbə qeydiyyatı yarat
        registration = self.env['edde.course.registration'].create(vals)
        
        # Lead-i Won olaraq qeyd et
        self.action_set_won()
        
        # Qeydiyyat formasını aç
        return {
            'name': 'Tələbə Qeydiyyatı',
            'view_mode': 'form',
            'res_model': 'edde.course.registration',
            'res_id': registration.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }