{
    'name': 'ZK Attendance Funcionalidad Extendida',
    'version': '15.0.1.0.2',
    'category': 'Human Resources',
    'summary': 'Extiende el control de asistencia biométrica por edificio',
    'author': 'Sebastián Paredes',
    'depends': ['hr_zk_attendance', 'hr_attendance'],
    'data': [
        'views/hr_attendance_views.xml',
        'views/hr_attendance_incomplete_views.xml'
    ],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}