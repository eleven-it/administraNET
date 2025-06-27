from odoo import api, SUPERUSER_ID
import logging

def migrate_address_to_building(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger = logging.getLogger(__name__)
    count = 0
    attendances = env['hr.attendance'].search([('building_id', '=', False), ('address_id', '!=', False)])
    for att in attendances:
        building = env['hr.zk.building'].search([('responsible_id', '=', att.address_id.id)], limit=1)
        if building:
            att.building_id = building.id
            count += 1
    _logger.info('Migración address_id -> building_id completada. Registros actualizados: %s', count) 