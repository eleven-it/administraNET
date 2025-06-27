{
    "name": "HR ZK Attendance FU",
    "version": "15.0.1.0.6",
    "depends": ["hr_attendance"],
    "author": "Sebastián Paredes",
    "category": "Human Resources",
    "description": "Extensión del módulo de asistencias para permitir múltiples fichadas por día y cálculo por edificio.",
    "data": [
        "security/ir.model.access.csv",
        "views/hr_attendance_views.xml",
        "views/hr_attendance_report_view.xml",
        "data/ir_cron_inherit.xml",
        "data/ir_model_data.xml"      
    ],
    "installable": True,
    "auto_install": False
}
