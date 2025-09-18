from odoo import models, fields, api

class Partner(models.Model):
    _inherit = 'res.partner'
    
    # Student related fields
    is_teacher = fields.Boolean(string="Müəllim", default=False)
    program_id = fields.Many2one('course.program', string='Program')
    university_id = fields.Many2one('res.partner', string='Universitet')
    student_country_id = fields.Many2one('course.country', string='Ölkə')  # Changed from country_id to avoid conflicts
    course_id = fields.Many2one('course.course', string='Kurs')
    source_id = fields.Many2one('course.source', string='Mənbə')
    
    # Button action to create a student registration
    def action_create_student(self):
        """
        Open the student registration form with pre-filled data from the contact
        """
        self.ensure_one()
        
        # Create a new student registration with this contact
        vals = {
            'student_id': self.id,
            'phone': self.phone,
            'phone2': self.mobile,
            'email': self.email,
            'program': self.program_id.id if self.program_id else False,
            'university': self.university_id.id if self.university_id else False,
            'course': self.course_id.id if self.course_id else False,
            'source': self.source_id.id if self.source_id else False,
            'country': self.student_country_id.id if self.student_country_id else False,
        }
        
        # Create the registration
        registration = self.env['edde.course.registration'].create(vals)
        
        # Return an action to open the newly created registration form
        return {
            'name': 'Tələbə Qeydiyyatı',
            'view_mode': 'form',
            'res_model': 'edde.course.registration',
            'res_id': registration.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }