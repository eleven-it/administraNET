# hr_zk_attendance_fu/models/zk_machine_inherit.py

from odoo import models

class ZkMachine(models.Model):
    _inherit = 'zk.machine'

    def action_download_attendance(self):
        """
        Redirección desde botón en la vista. Usa la lógica centralizada de hr.attendance.
        """
        return self.env['hr.attendance'].download_attendance()

    def cron_download(self):
        """
        Redefinición del cron: no hace nada local, llama directamente a la nueva lógica.
        """
        self.env['hr.attendance'].download_attendance()
