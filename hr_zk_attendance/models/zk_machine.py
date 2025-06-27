import pytz
import sys
import datetime
import logging
import binascii

from . import zklib
from .zkconst import *
from struct import unpack
from contextlib import contextmanager
from odoo import api, fields, models
from odoo import _
from odoo.exceptions import UserError, ValidationError
_logger = logging.getLogger(__name__)
try:
    from zk import ZK, const
except ImportError:
    _logger.error("Please Install pyzk library.")

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    device_id = fields.Char(string='Biometric Device ID')


class ZkMachine(models.Model):
    _name = 'zk.machine'
    
    name = fields.Char(string='Machine IP', required=True)
    port_no = fields.Integer(string='Port No', required=True)
    address_id = fields.Many2one('res.partner', string='Working Address', required=False, readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)

    def device_connect(self, zk):
        try:
            conn = zk.connect()
            return conn
        except Exception as e:
            _logger.error("Error connecting to device: %s", e)
            return False
        
    
    @api.model
    def _convert_timestamp(self, ts):
        """Helper para convertir el timestamp del dispositivo a string en UTC."""
        # Asumimos que ts es un objeto datetime del dispositivo
        atten_time = datetime.strptime(ts.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
        local_tz = pytz.timezone(self.env.user.partner_id.tz or 'GMT')
        local_dt = local_tz.localize(atten_time, is_dst=None)
        utc_dt = local_dt.astimezone(pytz.utc)
        utc_str = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
        # Convertir de nuevo a objeto datetime y a string con formato Odoo
        final_dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
        return fields.Datetime.to_string(final_dt)

    @contextmanager
    def open_connection(self, zk):
        """Context manager para manejar la conexión al dispositivo."""
        conn = self.device_connect(zk)
        try:
            yield conn
        finally:
            if conn:
                conn.disconnect()

    def clear_attendance(self):
        for info in self:
            try:
                machine_ip = info.name
                zk_port = info.port_no
                timeout = 10
                try:
                    zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=True)
                except NameError:
                    raise UserError(_("Please install it with 'pip3 install pyzk'."))

                # Intentamos establecer conexión con el dispositivo
                conn = self.device_connect(zk)
                if not conn:
                    raise UserError(_('Unable to connect to Attendance Device. Please use Test Connection button to verify.'))

                conn.enable_device()

                # Obtenemos el log de asistencias usando la conexión activa
                attendance_log = conn.get_attendance()

                if not attendance_log:
                    conn.disconnect()
                    # Devuelve una notificación informando que no se encontraron registros
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Clear Attendance'),
                            'message': _('No attendance records found on the device.'),
                            'sticky': False,
                        },
                    }
                
                # Si existen registros, intentamos limpiar el log en el dispositivo
                try:
                    conn.clear_attendance()
                except Exception as e:
                    _logger.error("Error while clearing attendance on device: %s", e)
                    raise UserError(_('Error while clearing attendance on device: %s') % e)
                
                # Borramos los registros en la base de datos local y obtenemos la cantidad eliminada
                self._cr.execute("""DELETE FROM zk_machine_attendance""")
                count_deleted = self._cr.rowcount
                conn.disconnect()
                
                # Devuelve una notificación con la cantidad de registros eliminados
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Clear Attendance'),
                        'message': _('%d attendance records were deleted.') % count_deleted,
                        'sticky': False,
                    },
                }
            except Exception as e:
                _logger.error("Error in clear_attendance: %s", e)
                raise ValidationError(_('Unable to clear Attendance log. Please check the connection to the device and that it has records.'))

    def getSizeUser(self, zk):
        """Checks a returned packet to see if it returned CMD_PREPARE_DATA,
        indicating that data packets are to be sent

        Returns the amount of bytes that are going to be sent"""
        command = unpack('HHHH', zk.data_recv[:8])[0]
        if command == CMD_PREPARE_DATA:
            size = unpack('I', zk.data_recv[8:12])[0]
            print("size", size)
            return size
        else:
            return False

    def zkgetuser(self, zk):
        """Start a connection with the time clock"""
        try:
            users = zk.get_users()
            print(users)
            return users
        except:
            return False

    @api.model
    def cron_download(self):
        machines = self.env['zk.machine'].search([])
        for machine in machines :
            machine.download_attendance()
            
    def download_attendance(self):
        _logger.info("++++++++++++Download Attendance Cron Executed++++++++++++++++++++++")
        zk_attendance_model = self.env['zk.machine.attendance']
        hr_attendance_model = self.env['hr.attendance']
        count_downloaded = 0

        self.ensure_one()
        try:
            zk = ZK(self.name, port=self.port_no, timeout=15, password=0, force_udp=False, ommit_ping=True)
        except NameError:
            raise UserError(_("Pyzk module not found. Please install it with 'pip3 install pyzk'."))

        with self.open_connection(zk) as conn:
            if not conn:
                raise UserError(_('Unable to connect, please check the parameters and network connections.'))

            try:
                users = conn.get_users()
            except Exception as e:
                _logger.warning("Error getting users: %s", e)
                users = None

            try:
                attendance_records = conn.get_attendance()
            except Exception as e:
                _logger.warning("Error getting attendance records: %s", e)
                attendance_records = None

            if not attendance_records:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Download Attendance'),
                        'message': _('No attendance records found on the device.'),
                        'sticky': False,
                    },
                }

            # Pre-cargar empleados existentes en un diccionario (clave: device_id)
            employee_records = self.env['hr.employee'].search([('device_id', '!=', False)])
            employee_dict = {str(emp.device_id): emp for emp in employee_records}

            # Pre-cargar usuarios del dispositivo (clave: device_id) para obtener información al crear nuevos empleados
            user_dict = {}
            if users:
                for user in users:
                    user_dict[str(user.user_id)] = user

            for rec in attendance_records:
                # Convertir el timestamp del registro usando el helper
                atten_time = self._convert_timestamp(rec.timestamp)
                device_uid = str(rec.user_id)

                # Buscar empleado existente por device_id
                emp = employee_dict.get(device_uid)
                if not emp:
                    # Si no existe, y tenemos información del usuario, crearlo
                    if device_uid in user_dict:
                        user_info = user_dict[device_uid]
                        emp = self.env['hr.employee'].create({
                            'device_id': device_uid,
                            'name': user_info.name or "Employee " + device_uid,
                        })
                        employee_dict[device_uid] = emp
                    else:
                        # Si tampoco hay información de usuario, saltar este registro
                        continue

                # Evitar duplicados: verificar si ya existe un registro para este dispositivo y hora
                duplicate = zk_attendance_model.search([
                    ('device_id', '=', device_uid),
                    ('punching_time', '=', atten_time)
                ], limit=1)
                if duplicate:
                    continue

                zk_attendance_model.create({
                    'employee_id': emp.id,
                    'device_id': device_uid,
                    'attendance_type': str(rec.status),
                    'punch_type': str(rec.punch),
                    'punching_time': atten_time,
                    'address_id': self.address_id.id,
                })
                count_downloaded += 1

                # Validar antes de crear/actualizar en hr.attendance
                # Si es check-out y la hora es inválida, solo crear inconsistencia y continuar
                if rec.punch == 1 and hasattr(rec, 'check_out') and hasattr(rec, 'check_in') and rec.check_out and rec.check_in and rec.check_out < rec.check_in:
                    self.env['hr.attendance.inconsistency'].create({
                        'employee_id': emp.id,
                        'check_in': rec.check_in.replace(tzinfo=None) if rec.check_in and rec.check_in.tzinfo else rec.check_in,
                        'check_out': rec.check_out.replace(tzinfo=None) if rec.check_out and rec.check_out.tzinfo else rec.check_out,
                        'motivo': _('Check-out time is earlier than check-in time.'),
                        'machine_id': self.id,
                        'building_id': getattr(self, 'building_id', False) and self.building_id.id or False,
                    })
                    continue

                # Actualizar el registro en hr.attendance:
                # Si punch == 0 (check-in) y no existe un registro abierto, crear uno.
                # Si punch == 1 (check-out) y existe un registro abierto, actualizarlo.
                att_var = hr_attendance_model.search([
                    ('employee_id', '=', emp.id),
                    ('check_out', '=', False)
                ], limit=1)
                if rec.punch == 0:  # check-in
                    check_in_val = datetime.strptime(atten_time, '%Y-%m-%d %H:%M:%S')
                    # Buscar registro abierto (sin check-out) en el mismo edificio
                    open_attendance = hr_attendance_model.search([
                        ('employee_id', '=', emp.id),
                        ('check_out', '=', False),
                        ('building_id', '=', getattr(self, 'building_id', False) and self.building_id.id or False)
                    ], order='check_in desc', limit=1)
                    if open_attendance:
                        self.env['hr.attendance.inconsistency'].create({
                            'employee_id': emp.id,
                            'check_in': check_in_val,
                            'motivo': _('Attempted check-in with previous open attendance in the same building.'),
                            'machine_id': self.id,
                            'building_id': getattr(self, 'building_id', False) and self.building_id.id or False,
                        })
                        continue
                    # Buscar registros solapados en el mismo edificio
                    overlapping_attendance = hr_attendance_model.search([
                        ('employee_id', '=', emp.id),
                        ('building_id', '=', getattr(self, 'building_id', False) and self.building_id.id or False),
                        '|',
                        ('check_out', '=', False),
                        ('check_out', '>', check_in_val),
                        ('check_in', '<=', check_in_val),
                    ], limit=1)
                    if overlapping_attendance:
                        self.env['hr.attendance.inconsistency'].create({
                            'employee_id': emp.id,
                            'check_in': check_in_val,
                            'motivo': _('Attempted check-in overlapping with another attendance in the same building.'),
                            'machine_id': self.id,
                            'building_id': getattr(self, 'building_id', False) and self.building_id.id or False,
                        })
                        continue
                    hr_attendance_model.create({
                        'employee_id': emp.id,
                        'check_in': check_in_val,
                        'building_id': getattr(self, 'building_id', False) and self.building_id.id or False,
                    })
                elif rec.punch == 1:  # check-out
                    if att_var:
                        # Validar que la hora de salida no sea menor que la de entrada
                        check_in_val = att_var.check_in
                        check_out_val = datetime.strptime(atten_time, '%Y-%m-%d %H:%M:%S')
                        if check_out_val < check_in_val:
                            self.env['hr.attendance.inconsistency'].create({
                                'employee_id': emp.id,
                                'check_in': check_in_val,
                                'check_out': check_out_val,
                                'motivo': _('Check-out time is earlier than check-in time.'),
                                'machine_id': self.id,
                                'building_id': getattr(self, 'building_id', False) and self.building_id.id or False,
                            })
                            continue
                        att_var.write({'check_out': check_out_val})
            # Fin de la iteración sobre registros

        _logger.info("++++++++++++Download Attendance Cron Finished. %d records processed.++++++++++++++++++++++", count_downloaded)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Download Attendance'),
                'message': _('%d attendance records were downloaded.') % count_downloaded,
                'sticky': False,
            },
        }


    def upload_employees(self):
        """
        Sube o actualiza empleados en el dispositivo usando el campo device_id.
        Se registra el inicio y fin del proceso y se retorna una notificación con el total procesado.
        """
        self.ensure_one()
        _logger.info("++++++++++++Upload Employees Cron Executed++++++++++++++++++++++")
        count_uploaded = 0

        try:
            zk = ZK(self.name, port=self.port_no, timeout=30, password=0, force_udp=False, ommit_ping=True)
        except NameError:
            raise UserError(_("Pyzk module not found. Please install it with 'pip3 install pyzk'."))

        with self.open_connection(zk) as conn:
            if not conn:
                raise UserError(_("Could not connect to the device."))
            # Filtrar solo empleados que tengan definido un device_id
            employees = self.env["hr.employee"].search([('device_id', '!=', False)])
            for emp in employees:
                try:
                    uid = int(emp.device_id)
                except ValueError:
                    _logger.warning("Employee %s has a non-integer device_id: %s. Skipping.", emp.name, emp.device_id)
                    continue

                conn.set_user(uid=uid, name=emp.name, privilege=const.USER_DEFAULT, password="")
                _logger.info("Employee %s with device_id %s uploaded/updated in device %s", emp.name, uid, self.name)
                count_uploaded += 1

        _logger.info("++++++++++++Upload Employees Cron Finished. %d employees processed.++++++++++++++++++++++", count_uploaded)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Upload Employees'),
                'message': _('%d employees were uploaded/updated.') % count_uploaded,
                'sticky': False,
            }
        }

    def download_employees(self):
        """
        Descarga los usuarios registrados en el dispositivo y sincroniza empleados en Odoo
        utilizando el campo device_id para evitar duplicados.
        Se registra el inicio y fin del proceso y se retorna una notificación con el total descargado.
        """
        self.ensure_one()
        _logger.info("++++++++++++Download Employees Cron Executed++++++++++++++++++++++")
        count_downloaded = 0

        try:
            zk = ZK(self.name, port=self.port_no, timeout=30, password=0, force_udp=False, ommit_ping=True)
        except NameError:
            raise UserError(_("Pyzk module not found. Please install it with 'pip3 install pyzk'."))

        with self.open_connection(zk) as conn:
            if not conn:
                raise UserError(_("Could not connect to the device."))

            users = conn.get_users()
            if not users:
                _logger.info("No employees found on device.")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Download Employees'),
                        'message': _('No employees found on the device.'),
                        'sticky': False,
                    },
                }

            # Pre-cargar empleados existentes en Odoo en un diccionario (clave: device_id)
            employee_records = self.env["hr.employee"].search([('device_id', '!=', False)])
            emp_dict = {str(emp.device_id): emp for emp in employee_records}

            for user in users:
                device_uid = str(user.uid)
                if device_uid in emp_dict:
                    _logger.info("Employee %s (device_id: %s) already exists in Odoo. Skipping.", user.name, device_uid)
                    continue

                new_employee = self.env["hr.employee"].create({
                    "name": user.name or "Employee " + device_uid,
                    "device_id": device_uid,
                })
                _logger.info("Employee %s (device_id: %s) added to Odoo.", user.name, device_uid)
                count_downloaded += 1

        _logger.info("++++++++++++Download Employees Cron Finished. %d employees processed.++++++++++++++++++++++", count_downloaded)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Download Employees'),
                'message': _('%d employees were downloaded.') % count_downloaded,
                'sticky': False,
            }
        }