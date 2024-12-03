from PyQt5.QtCore import QThread, pyqtSignal
import time
import random
import csv
from dba import DBA_Simulator, ONU
from network_nodes import ONUNode

class UploadSimulation(QThread):
    updatePathSignal = pyqtSignal(str)

    def __init__(self, onu_ids, components: dict[str, ONUNode], speed=0.1):
        super().__init__()
        self.onu_ids = onu_ids
        self.components = components
        self.speed = speed
        self.running = True
        self.traffic = []
        self.history = []
        
        ONUs = []
        for onu_id in onu_ids:
            ONUs.append(ONU(onu_id, buffer_size=10, max_bw=components[onu_id].bandwidth, proportions=components[onu_id].traffic_proportions))
        
        self.dba_simulator = DBA_Simulator(
            ONUS=ONUs,
            groups=[self.onu_ids],
            Tm=0.0025
        )

    def run(self):
        while self.running:
            allocations = self.dba_simulator.simulate_cycle()
            self.history.append(allocations)

            for onu_id, allocation in allocations.items():
                total_allocated_bw = sum(allocation.values())
                if total_allocated_bw > 0:
                    self.updatePathSignal.emit(onu_id)
                    
                    time.sleep(total_allocated_bw/self.speed)
            # Sleep between cycles
            time.sleep(0.5)

    def stop(self):
        self.running = False

    def export_history(self, file_path):
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['iteration', 'onu ID', 'FT1', 'FT2', 'FT3', 'FT4', 'FTtotal', 'BWexcess', 'Avg Latency', 'Max Transfer Rate']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            
            for iteration, allocations in enumerate(self.history, start=1):
                for onu_id, alloc in allocations.items():
                    ft1 = alloc.get(1, 0)
                    ft2 = alloc.get(2, 0)
                    ft3 = alloc.get(3, 0)
                    ft4 = alloc.get(4, 0)
                    fttotal = ft1 + ft2 + ft3 + ft4
                    onu = self.dba_simulator.ONUs[onu_id]
                    avg_latency = (onu.total_latency / onu.packets_transmitted) if onu.packets_transmitted > 0 else 0
                    max_transfer_rate = onu.max_allocated_bw
                    writer.writerow({
                        'iteration': iteration,
                        'onu ID': onu_id,
                        'FT1': ft1,
                        'FT2': ft2,
                        'FT3': ft3,
                        'FT4': ft4,
                        'FTtotal': fttotal,
                        'BWexcess': self.components[onu_id].bandwidth - fttotal if fttotal < self.components[onu_id].bandwidth else 0,
                        'Avg Latency': avg_latency,
                        'Max Transfer Rate': max_transfer_rate
                    })
