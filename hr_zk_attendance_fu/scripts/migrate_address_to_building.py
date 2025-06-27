# -*- coding: utf-8 -*-
'''
Script de migración: address_id (res.partner) -> building_id (hr.zk.building)
Debe ejecutarse con el entorno Odoo cargado (por ejemplo, con shell o como server action temporal).
Genera un log en migrate_building_log.txt con los registros no migrados.
'''
from odoo import api, SUPERUSER_ID
import os

def migrate_address_to_building(env):
    Machine = env['zk.machine']
    Building = env['hr.zk.building']
    Attendance = env['hr.attendance']

    log_path = os.path.abspath('migrate_building_log.txt')
    log_lines = []
    address_map = {}
    for machine in Machine.search([]):
        partner = machine.address_id
        if not partner:
            continue
        # Buscar o crear edificio
        building = Building.search([('code', '=', partner.ref or partner.id)], limit=1)
        if not building:
            building = Building.create({
                'code': partner.ref or str(partner.id),
                'name': partner.name,
                'street': partner.street or '',
                'responsible_id': partner.id if partner else False,
            })
            log_lines.append(f"CREATED BUILDING: {building.code} - {building.name}")
        else:
            log_lines.append(f"FOUND BUILDING: {building.code} - {building.name}")
        address_map[partner.id] = building.id
        # Actualizar el reloj
        machine.building_id = building.id
        log_lines.append(f"MACHINE {machine.name} ({machine.device_id}) -> BUILDING {building.code}")
    # 2. Actualizar asistencias existentes
    for att in Attendance.search([]):
        if att.building_id:
            continue
        # Buscar por el reloj asociado
        if hasattr(att, 'device_id') and att.device_id:
            machine = Machine.search([('device_id', '=', att.device_id)], limit=1)
            if machine and machine.building_id:
                att.building_id = machine.building_id.id
                log_lines.append(f"ATTENDANCE {att.id} ({att.employee_id.name}) -> BUILDING {machine.building_id.code}")
            else:
                log_lines.append(f"UNMIGRATED ATTENDANCE: {att.id} (device_id={att.device_id}, employee={att.employee_id.name}) - NO MACHINE FOUND")
        else:
            log_lines.append(f"UNMIGRATED ATTENDANCE: {att.id} (employee={att.employee_id.name}) - NO DEVICE_ID")
    # Guardar log
    with open(log_path, 'w', encoding='utf-8') as f:
        for line in log_lines:
            f.write(line + '\n')
    print(f"Migration log saved to {log_path}")

# Para ejecutar desde shell Odoo:
# env = odoo.api.Environment(cr, SUPERUSER_ID, {})
# migrate_address_to_building(env) 