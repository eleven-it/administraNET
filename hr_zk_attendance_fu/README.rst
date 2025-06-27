============================
HR ZK Attendance FU
============================

This module extends Odoo's HR Attendance to support multiple biometric devices (ZKTeco) per building, allowing employees to clock in/out in different buildings and shifts on the same day. It introduces a Building model (code, name, address, maintenance responsible) and links each device and attendance to a building. Reports and views allow filtering and grouping by building and day. Data migration from previous address-based configuration is included.

**Dependencies:**
- hr_attendance (Odoo core)
- hr_zk_attendance (Biometric integration base)

----

**Spanish translation:**

Este módulo extiende la asistencia de Odoo para soportar múltiples relojes biométricos (ZKTeco) por edificio, permitiendo que los empleados fichen en diferentes edificios y turnos en un mismo día. Introduce un modelo de Edificio (código, nombre, dirección, responsable de mantenimiento) y vincula cada dispositivo y asistencia a un edificio. Los reportes y vistas permiten filtrar y agrupar por edificio y día. Incluye migración de datos desde la configuración previa basada en direcciones. 