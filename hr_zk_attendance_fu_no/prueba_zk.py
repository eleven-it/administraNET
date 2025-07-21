from zk import ZK
from collections import Counter

# Configura la conexión con tu dispositivo
zk = ZK('186.13.57.156', port=4370, timeout=5)
conn = None

try:
    conn = zk.connect()
    conn.disable_device()
    attendances = conn.get_attendance()

    # Contar los diferentes tipos de asistencia
    att_type_counter = Counter()
    for att in attendances:
        att_type = getattr(att, 'attendance_type', 'Desconocido')
        att_type_counter[att_type] += 1

    # Mostrar los resultados
    print("Tipos de asistencia encontrados:")
    for att_type, count in att_type_counter.items():
        print(f"Tipo: {att_type} - Cantidad: {count}")

finally:
    if conn:
        conn.enable_device()
        conn.disconnect()
