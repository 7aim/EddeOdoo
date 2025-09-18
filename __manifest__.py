{
    'name': 'EDDE Course Management',
    'version': '2.0',
    'summary': 'Course and Registration Management for EDDE',
    'description': """
        This module provides management capabilities for courses and student registrations.
    """,
    'category': 'Education',
    'author': 'EDDE',
    'website': '',
    'depends': ['base', 'contacts', 'mail', 'crm'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/course_registration_views.xml',
        'views/course_config_views.xml',
        'views/course_group_views.xml',
        'views/res_partner_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}