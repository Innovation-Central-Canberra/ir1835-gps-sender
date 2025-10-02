#!/usr/bin/env python3
import socket
import time
import json
import sys
import requests
from datetime import datetime
import threading

# Configuration - UPDATE THIS IP ADDRESS
AZURE_SERVER_URL = "http://20.211.145.100:80/gps"
UDP_PORT = 4001
DEVICE_ID = "IR1835"
SEND_INTERVAL = 10  # Send data every 10 seconds (adjust as needed)
REQUEST_TIMEOUT = 10

class GPSSender:
    def __init__(self):
        self.latest_gps_data = None
        self.running = True
        self.data_lock = threading.Lock()
        self.last_send_time = 0
        
    def parse_gps_from_nmea(self, line, sender_ip):
        """Parse GPS data from NMEA sentence - same logic as gpsreader.py"""
        try:
            if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                parts = line.split(',')
                if len(parts) > 6 and parts[2] and parts[4]:
                    # Parse latitude
                    lat = float(parts[2][:2]) + float(parts[2][2:]) / 60
                    if parts[3] == 'S':
                        lat = -lat
                    
                    # Parse longitude  
                    lon = float(parts[4][:3]) + float(parts[4][3:]) / 60
                    if parts[5] == 'W':
                        lon = -lon
                    
                    # Extract additional data
                    altitude = None
                    satellites = None
                    fix_quality = None
                    
                    if len(parts) > 9 and parts[9]:
                        try:
                            altitude = float(parts[9])
                        except ValueError:
                            pass
                    
                    if len(parts) > 7 and parts[7]:
                        try:
                            satellites = int(parts[7])
                        except ValueError:
                            pass
                    
                    if len(parts) > 6 and parts[6]:
                        try:
                            fix_quality_code = int(parts[6])
                            fix_quality = {
                                0: 'Invalid',
                                1: 'GPS',
                                2: 'DGPS',
                                3: 'PPS',
                                4: 'RTK',
                                5: 'Float RTK',
                                6: 'Estimated'
                            }.get(fix_quality_code, f'Unknown({fix_quality_code})')
                        except ValueError:
                            pass
                    
                    gps_data = {
                        "device_id": DEVICE_ID,
                        "timestamp": datetime.now().isoformat(),
                        "latitude": lat,
                        "longitude": lon,
                        "altitude": altitude,
                        "satellites": satellites,
                        "fix_quality": fix_quality,
                        "source": "UDP_NMEA",
                        "sender_ip": sender_ip,
                        "raw_nmea": line
                    }
                    
                    return gps_data
                    
        except (ValueError, IndexError) as e:
            print(f"Error parsing NMEA coordinates: {e}")
            
        return None
    
    def send_to_azure_server(self, gps_data):
        """Send GPS data to Azure Flask server"""
        try:
            response = requests.post(
                AZURE_SERVER_URL,
                json=gps_data,
                timeout=REQUEST_TIMEOUT,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"GPS data sent to Azure: {gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}")
                return True
            else:
                print(f"Azure server error: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            print("Timeout sending to Azure server")
        except requests.exceptions.ConnectionError:
            print("Connection error to Azure server")
        except Exception as e:
            print(f"Error sending to Azure server: {e}")
            
        return False
    
    def udp_listener(self):
        """Listen for GPS data on UDP port"""
        try:
            # Create UDP socket to receive NMEA data
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('0.0.0.0', UDP_PORT))
            sock.settimeout(5.0)  # 5 second timeout
            
            print(f"GPS UDP listener started - listening on port {UDP_PORT}")
            
            while self.running:
                try:
                    # Receive UDP packet
                    data, addr = sock.recvfrom(1024)
                    line = data.decode('ascii', errors='ignore').strip()
                    
                    if line.startswith('$'):
                        # print(f"NMEA (from {addr[0]}): {line}")
                        
                        # Parse GPS data from NMEA sentence
                        gps_data = self.parse_gps_from_nmea(line, addr[0])
                        
                        if gps_data:
                            with self.data_lock:
                                self.latest_gps_data = gps_data
                            
                            print(f"GPS Position: Lat={gps_data['latitude']:.6f}, Lon={gps_data['longitude']:.6f}")
                            
                            # Send immediately if it's been long enough since last send
                            current_time = time.time()
                            if current_time - self.last_send_time >= SEND_INTERVAL:
                                if self.send_to_azure_server(gps_data):
                                    self.last_send_time = current_time
                        
                except socket.timeout:
                    print("No GPS data received in last 5 seconds...")
                    continue
                except Exception as e:
                    print(f"Error receiving GPS data: {e}")
                    if self.running:
                        time.sleep(1)
                        
        except Exception as e:
            print(f"Failed to create UDP socket: {e}")
            self.running = False
    
    def periodic_sender(self):
        """Periodically send latest GPS data to Azure server"""
        print(f"Periodic sender started (interval: {SEND_INTERVAL} seconds)")
        
        while self.running:
            try:
                # Wait for the interval
                for i in range(SEND_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
                
                if not self.running:
                    break
                
                # Send latest GPS data if available
                with self.data_lock:
                    if self.latest_gps_data:
                        current_time = time.time()
                        # Only send if we haven't sent recently
                        if current_time - self.last_send_time >= SEND_INTERVAL:
                            if self.send_to_azure_server(self.latest_gps_data):
                                self.last_send_time = current_time
                    else:
                        print("No GPS data available to send to Azure")
                        
            except Exception as e:
                print(f"Error in periodic sender: {e}")
    
    def run(self):
        """Run the GPS sender"""
        print("="*60)
        print("         IR1835 GPS Sender to Azure")
        print("="*60)
        print(f"Device ID: {DEVICE_ID}")
        print(f"UDP Port: {UDP_PORT}")
        print(f"Azure Server: {AZURE_SERVER_URL}")
        print(f"Send Interval: {SEND_INTERVAL} seconds")
        print("="*60)
        
        try:
            # Start UDP listener in a separate thread
            listener_thread = threading.Thread(target=self.udp_listener, daemon=True)
            listener_thread.start()
            
            # Start periodic sender in main thread
            self.periodic_sender()
            
        except KeyboardInterrupt:
            print("\nShutting down GPS sender...")
        finally:
            self.running = False


if __name__ == "__main__":
    # Validate configuration
    if "YOUR_AZURE_VM_IP" in AZURE_SERVER_URL:
        print("ERROR: Please update AZURE_SERVER_URL with your actual Azure VM IP address!")
        print(f"Current URL: {AZURE_SERVER_URL}")
        sys.exit(1)
    
    # Test Azure server connectivity
    print("Testing connection to Azure server...")
    try:
        response = requests.get(AZURE_SERVER_URL.replace('/gps', '/health'), timeout=5)
        if response.status_code == 200:
            print("Azure server is reachable")
        else:
            print(f"Azure server responded with status {response.status_code}")
    except Exception as e:
        print(f"Cannot reach Azure server: {e}")
        print("Continuing anyway - will retry when GPS data is available")
    
    # Create and run GPS sender
    sender = GPSSender()
    sender.run()