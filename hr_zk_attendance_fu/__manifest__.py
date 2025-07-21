{
    "name": "HR ZK Attendance FU",
    "version": "15.0.1.0.8",
    "depends": ["hr_attendance", "hr_contract", "hr_zk_attendance"],
    "author": "Sebastián Paredes",
    "category": "Human Resources",
    "description": "Extensión del módulo de asistencias para permitir múltiples fichadas por día y cálculo por edificio.",
    "data": [
        "security/ir.model.access.csv",
        "views/hr_attendance_views.xml",
        "views/hr_attendance_report_view.xml",
        "views/zk_machine_inherit_views.xml",
        "views/building_views.xml",
        "views/hr_attendance_inconsistency_views.xml",
        "views/hr_attendance_inconsistency_action.xml",
        "views/hr_attendance_inconsistency_menu.xml",
        "data/ir_cron_inherit.xml",
        "data/ir_model_data.xml",
        "data/server_action_migrate_address_to_building.xml",
    ],
    "installable": True,
    "auto_install": False,
    "post_init_hook": "migrate_address_to_building"
}
