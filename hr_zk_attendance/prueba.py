#!/usr/bin/env python3
from zk import ZK, const
import sys

def test_clear_attendance(ip, port):
    print(f"Intentando conectar a {ip}:{port} ...")
    try:
        # Crear instancia de ZK con los parámetros de conexión
        zk = ZK(ip, port=port, timeout=30, password=0, force_udp=False, ommit_ping=False)
        conn = zk.connect()
        print("Conexión exitosa al dispositivo.")
    except Exception as e:
        print("Error de conexión:", e)
        sys.exit(1)

    try:
        # Habilitar el dispositivo si es necesario (algunos dispositivos requieren esto antes de operar)
        conn.enable_device()
        # Obtener el log de asistencias
        attendance = conn.get_attendance()
        if attendance:
            print(f"Se encontraron {len(attendance)} registros de asistencia en el dispositivo.")
            # Si el método clear_attendance existe, intentarlo
            if hasattr(conn, 'clear_attendance'):
                try:
                    conn.clear_attendance()
                    print("Registros de asistencia borrados exitosamente.")
                except Exception as e:
                    print("Error al limpiar registros:", e)
            else:
                print("El dispositivo no soporta la limpieza remota mediante clear_attendance().")
        else:
            print("No se encontraron registros de asistencia en el dispositivo.")
    except Exception as e:
        print("Error al obtener registros de asistencia:", e)
    finally:
        conn.disconnect()

if __name__ == "__main__":
    # Reemplaza por la IP/hostname y el puerto de tu dispositivo
    device_ip = "e1f30ecfe1c9.sn.mynetname.net"
    device_port = 4370
    test_clear_attendance(device_ip, device_port)

