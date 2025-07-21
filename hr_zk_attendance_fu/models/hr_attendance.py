# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import pytz
import logging

_logger = logging.getLogger(__name__)

try:
    from zk import ZK, const
except ImportError:
    _logger.error("Pyzk library not installed. Please run: pip install pyzk")


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    building_id = fields.Many2one("hr.zk.building", string="Building", required=False)

    attendance_inconsistency_count = fields.Integer(
        string="Inconsistencias",
        compute="_compute_inconsistency_count"
    )

    contract_id = fields.Many2one('hr.contract', string='Contract', compute='_compute_contract_id', store=True)

    @api.depends('employee_id', 'check_in')
    def _compute_contract_id(self):
        for att in self:
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', att.employee_id.id),
                ('state', '=', 'open'),
                ('date_start', '<=', att.check_in),
                '|', ('date_end', '=', False), ('date_end', '>=', att.check_in)
            ], limit=1)
            att.contract_id = contract.id if contract else False

    def _check_contract_active(self, raise_exception=True, inconsistencies_list=None):
        for att in self:
            # Nueva lógica: solo validar que el empleado tenga un plan de horas laborales (resource.calendar)
            calendar = att.employee_id.resource_calendar_id
            if not calendar:
                motivo = _('No working schedule assigned: This employee does not have a working schedule (resource calendar) assigned, so worked hours and overtime cannot be calculated.')
                suggestion = _('To resolve this, please assign a working schedule to the employee profile in the "Working Schedule" field. Without this, the system cannot calculate worked hours or overtime for this attendance.\n\nEmployee: %(empl)s\nBuilding: %(building)s\nCheck-in: %(checkin)s') % {
                    'empl': att.employee_id.name,
                    'building': att.building_id.display_name,
                    'checkin': att.check_in
                }
                self.env['hr.attendance.inconsistency'].create({
                    'employee_id': att.employee_id.id,
                    'check_in': att.check_in,
                    'check_out': att.check_out,
                    'building_id': att.building_id.id,
                    'motivo': motivo,
                    'suggestion': suggestion,
                    'state': 'pending',
                })
                if inconsistencies_list is not None:
                    inconsistencies_list.append({
                        'employee': att.employee_id.name,
                        'building': att.building_id.display_name,
                        'check_in': att.check_in,
                    })
            # Nunca lanzar excepción, solo registrar inconsistencia

    @api.model_create_multi
    def create(self, vals_list):
        context = self.env.context or {}
        is_massive = context.get('from_download_attendance', False)
        inconsistencies_list = context.get('inconsistencies_list')
        _logger.info(f"[CREATE] Context: {context}, is_massive: {is_massive}, vals_list: {vals_list}")
        records = super().create(vals_list)
        # Solo validar plan de horas laborales, nunca bloquear
        records._check_contract_active(raise_exception=False, inconsistencies_list=inconsistencies_list)
        return records

    @api.constrains('check_in', 'check_out', 'employee_id', 'building_id')
    def _check_validity(self):
        for attendance in self:
            # Solo una asistencia abierta por empleado, edificio y día
            checkin_date = attendance.check_in.date() if attendance.check_in else False
            open_attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('building_id', '=', attendance.building_id.id),
                ('check_out', '=', False),
                ('id', '!=', attendance.id),
                ('check_in', '>=', fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(fields.Date.to_string(checkin_date) + ' 00:00:00')))),
                ('check_in', '<=', fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(fields.Date.to_string(checkin_date) + ' 23:59:59')))),
            ], limit=1)
            if open_attendances:
                self.env['hr.attendance.inconsistency'].create({
                    'employee_id': attendance.employee_id.id,
                    'check_in': attendance.check_in,
                    'check_out': attendance.check_out,
                    'building_id': attendance.building_id.id,
                    'motivo': _('There is already an open attendance for this employee in this building.'),
                    'suggestion': _('Employee: %(empl)s, Building: %(building)s, Check-in: %(checkin)s. There is already an open attendance for this employee in this building. Please close the previous attendance before creating a new one.') % {
                        'empl': attendance.employee_id.name,
                        'building': attendance.building_id.display_name,
                        'checkin': attendance.check_in
                    },
                    'state': 'pending',
                })
                raise ValidationError(_('There is already an open attendance for this employee in this building.'))

            # Restricción de solapamiento de horarios por empleado y edificio
            # Buscar posibles candidatos y filtrar en Python para evitar falsos positivos
            candidates = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('building_id', '=', attendance.building_id.id),
                ('id', '!=', attendance.id),
                '|',
                ('check_out', '!=', False),
                ('check_out', '=', False),
            ])
            for overlap in candidates:
                # Definir los intervalos
                a_start = attendance.check_in
                a_end = attendance.check_out or attendance.check_in
                b_start = overlap.check_in
                b_end = overlap.check_out or overlap.check_in
                # Si ambos tienen check_out, comparar rangos
                if a_end and b_end and (a_start < b_end and a_end > b_start):
                    check_in_str = b_start and fields.Datetime.to_string(b_start) or '—'
                    check_out_str = b_end and fields.Datetime.to_string(b_end) or '—'
                    msg = _(
                        'There is an overlapping attendance for this employee in this building.\n'
                        'Conflicting record:\n'
                        '- Check In: %(checkin)s\n'
                        '- Check Out: %(checkout)s\n'
                        '- Building: %(building)s\n'
                        '- Employee: %(employee)s'
                    ) % {
                        'checkin': check_in_str,
                        'checkout': check_out_str,
                        'building': overlap.building_id.display_name or '',
                        'employee': overlap.employee_id.name or '',
                    }
                    self.env['hr.attendance.inconsistency'].create({
                        'employee_id': attendance.employee_id.id,
                        'check_in': attendance.check_in,
                        'check_out': attendance.check_out,
                        'building_id': attendance.building_id.id,
                        'motivo': msg,
                        'suggestion': _('Please adjust the times to avoid overlaps.'),
                        'state': 'pending',
                    })
                    raise ValidationError(msg)

    def _compute_inconsistency_count(self):
        for rec in self:
            rec.attendance_inconsistency_count = self.env['hr.attendance.inconsistency'].search_count([
                ('employee_id', '=', rec.employee_id.id),
                ('check_in', '=', rec.check_in),
                ('check_out', '=', rec.check_out),
            ])

    def _migrate_address_to_building(self):
        """Método para migrar address_id a building_id"""
        _logger = logging.getLogger(__name__)
        count = 0
        attendances = self.search([('building_id', '=', False), ('address_id', '!=', False)])
        for att in attendances:
            building = self.env['hr.zk.building'].search([('responsible_id', '=', att.address_id.id)], limit=1)
            if building:
                att.building_id = building.id
                count += 1
        _logger.info('Migración address_id -> building_id completada. Registros actualizados: %s', count)
        return True

    @api.model
    def download_attendance(self):
        zk_machine_model = self.env['zk.machine']
        zk_attendance_model = self.env['zk.machine.attendance'] if 'zk.machine.attendance' in self.env else None
        hr_employee_model = self.env['hr.employee']

        # Buscar todas las máquinas (sin filtro por 'state')
        machines = zk_machine_model.search([])
        total_downloaded = 0
        inconsistencies = []

        for machine in machines:
            _logger.info("Connecting to device %s:%s", machine.name, machine.port_no)

            try:
                zk = ZK(machine.name, port=machine.port_no, timeout=20, password=0, force_udp=False, ommit_ping=True)
                conn = zk.connect()
                conn.disable_device()
                users = conn.get_users()
                records = conn.get_attendance()
            except Exception as e:
                _logger.warning("Failed to connect or fetch data from device %s: %s", machine.name, str(e))
                continue

            if not records:
                _logger.info("No attendance records found for device %s", machine.name)
                conn.enable_device()
                conn.disconnect()
                continue

            user_dict = {str(u.user_id): u for u in users}
            employees = hr_employee_model.search([('device_id', '!=', False)])
            emp_dict = {str(e.device_id): e for e in employees}

            for rec in records:
                timestamp = rec.timestamp
                device_uid = str(rec.user_id)

                local_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_dt = local_tz.localize(timestamp)
                atten_time = local_dt.astimezone(pytz.utc)

                employee = emp_dict.get(device_uid)
                if not employee and device_uid in user_dict:
                    user_data = user_dict[device_uid]
                    employee = hr_employee_model.create({
                        'name': user_data.name or f"Employee {device_uid}",
                        'device_id': device_uid
                    })
                    emp_dict[device_uid] = employee
                    _logger.info("Created new employee: %s", employee.name)

                if not employee:
                    _logger.warning("Employee with device_id %s not found and cannot be created", device_uid)
                    continue

                if zk_attendance_model:
                    existing_zk = zk_attendance_model.search([
                        ('device_id', '=', device_uid),
                        ('punching_time', '=', atten_time)
                    ], limit=1)
                    if not existing_zk:
                        zk_attendance_model.create({
                            'employee_id': employee.id,
                            'device_id': device_uid,
                            'attendance_type': str(rec.status),
                            'punch_type': str(rec.punch),
                            'punching_time': atten_time,
                            'address_id': machine.address_id.id,
                        })

                existing_attendance = self.search([
                    ('employee_id', '=', employee.id),
                    ('check_out', '=', False),
                    ('building_id', '=', machine.building_id.id)
                ], limit=1)

                if rec.punch == 0:  # Check-in
                    if not existing_attendance:
                        try:
                            self.with_context(from_download_attendance=True, inconsistencies_list=inconsistencies).create({
                                'employee_id': employee.id,
                                'check_in': atten_time,
                                'building_id': machine.building_id.id,
                            })
                            total_downloaded += 1
                        except Exception as e:
                            _logger.warning(f"Error creating attendance for {employee.name}: {str(e)}")
                elif rec.punch == 1:  # Check-out
                    if existing_attendance and atten_time > existing_attendance.check_in:
                        try:
                            existing_attendance.write({'check_out': atten_time})
                            total_downloaded += 1
                        except Exception as e:
                            _logger.warning(f"Error updating check_out for {employee.name}: {str(e)}")

            conn.enable_device()
            conn.disconnect()
            _logger.info("Processed device %s. Records downloaded: %d", machine.name, total_downloaded)

        # Construir mensaje resumen
        msg = _('%d attendance records were processed.') % total_downloaded
        if inconsistencies:
            msg += '<br/><b>' + _('Attendances not created due to missing contract:') + '</b><ul>'
            for inc in inconsistencies:
                msg += f"<li>{inc['employee']} ({inc['building']}, {inc['check_in']})</li>"
            msg += '</ul>'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Download Attendance'),
                'message': msg,
                'sticky': False,
            },
        }
