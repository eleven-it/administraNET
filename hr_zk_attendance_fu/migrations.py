from odoo.api import Environment
from odoo import _

def migrate_address_to_building(cr, registry):
    env = Environment(cr, 1, {})
    Attendance = env['hr.attendance']
    Building = env['hr.zk.building']
    Contract = env['hr.contract']
    for att in Attendance.search([('building_id', '=', False)]):
        # Ejemplo: buscar edificio por responsable (puedes adaptar la lógica según tus datos)
        building = False
        if hasattr(att, 'address_id') and att.address_id:
            building = Building.search([('responsible_id', '=', att.address_id.id)], limit=1)
        if building:
            att.building_id = building.id
        # Asociar contrato activo si no está seteado
        if not att.contract_id:
            contract = Contract.search([
                ('employee_id', '=', att.employee_id.id),
                ('state', '=', 'open'),
                ('date_start', '<=', att.check_in),
                '|', ('date_end', '=', False), ('date_end', '>=', att.check_in)
            ], limit=1)
            if contract:
                att.contract_id = contract.id 