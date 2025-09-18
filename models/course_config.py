from odoo import models, fields

class CourseProgram(models.Model):
    _name = 'course.program'
    _description = 'Course Program'
    
    name = fields.Char('Program adı', required=True)
    description = fields.Text('Təsvir')
    active = fields.Boolean(default=True)


class CourseCourse(models.Model):
    _name = 'course.course'
    _description = 'Course'
    
    name = fields.Char('Kurs adı', required=True)
    description = fields.Text('Təsvir')
    program_id = fields.Many2one('course.program', string='Program')
    active = fields.Boolean(default=True)


class CourseSource(models.Model):
    _name = 'course.source'
    _description = 'Student Source'
    
    name = fields.Char('Mənbə', required=True)
    description = fields.Text('Təsvir')
    active = fields.Boolean(default=True)


class CourseCountry(models.Model):
    _name = 'course.country'
    _description = 'Student Country'
    
    name = fields.Char('Ölkə', required=True)