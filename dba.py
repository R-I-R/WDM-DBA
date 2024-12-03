import random
from enum import Enum

class TCont(Enum):
    T1 = 1
    T2 = 2
    T3 = 3
    T4 = 4


class Packet:
    def __init__(self, size:int):
        self.size:int = size
        
class ONU:
    def __init__(self, onu_id, buffer_size, max_bw, proportions: dict[TCont,float] | None = None):
        self.onu_id = onu_id
        self.buffer_size: int = buffer_size
        self.max_bw: float = max_bw
        if proportions:
            self.proportions = proportions
        else:
            self.proportions: dict[TCont,float] = {1: 0, 2: 0, 3: 0, 4: 0}
        self.HCT: dict[TCont,list[int]] = {1: [], 2: [], 3: [], 4: []}
        self.avg_HCT: dict[TCont,float] = {1: 0, 2: 0, 3: 0, 4: 0}
        self.queue: dict[TCont,list[Packet]] = {1: [], 2: [], 3: [], 4: []}
        
    def update_HCT(self):
        for t in TCont:
            t = t.value
            if len(self.HCT[t]) >= self.buffer_size:
                self.HCT[t] = self.HCT[t][-self.buffer_size:]
            total_t = sum(pkt.size for pkt in self.queue[t])
            self.HCT[t].append(total_t)
            # Update avg_HCT
            self.avg_HCT[t] = sum(self.HCT[t])/len(self.HCT[t]) if len(self.HCT[t]) > 0 else 0

    def get_RT(self):
        RT: dict[TCont,int] = {}
        for t in TCont:
            t = t.value
            RT[t] = sum(pkt.size for pkt in self.queue[t])
        return RT

class DBA_Simulator:
    def __init__(self, ONUS: list[ONU], groups: list[list[str]]):
        self.N: int = len(ONUS)  # number of ONUs
        self.groups: list[list[str]] = groups
        # self.num_groups = num_groups
        self.ONUs: dict[str,ONU] = {}
        for onu in ONUS:
            self.ONUs[onu.onu_id] = onu

    def traffic_generator(self):
        # For each ONU
        for onu_id, onu in self.ONUs.items():
            # Total traffic to be generated for this ONU
            total_packets = random.randint(0,10)
            # Generate traffic according to the proportions
            proportions = onu.proportions
            total_proportion = sum(proportions.values())
            num_packets_per_TCont = {}
            for t in TCont:
                num_packets_per_TCont[t.value] = int(total_packets * proportions.get(t.value,0)/total_proportion)
            
            remaining_packets = total_packets - sum(num_packets_per_TCont.values())
            
            # Distribute remaining packets randomly
            for _ in range(remaining_packets):
                t = random.choice([2,3,4])
                num_packets_per_TCont[t] +=1
            # Generate the packets
            for t in TCont:
                t = t.value
                for _ in range(num_packets_per_TCont[t]):
                    pkt_size = random.randint(1, onu.max_bw*10)/1000
                    self.ONUs[onu_id].queue[t].append(Packet(pkt_size))

    def DBA(self):
        allocations: dict[str,dict[TCont,float]] = {}
        for group in self.groups:
            # Update HCT for ONUs in this group
            for onu_id in group:
                self.ONUs[onu_id].update_HCT()
            # Initialize data structures
            group_PT: dict[str,dict[TCont,int]] = {}
            group_FT: dict[str,dict[TCont,float]] = {}
            group_allocations = {}
            group_Bexcess = 0
            lightly_loaded_onus: list[str] = []
            heavily_loaded_onus: list[str] = []
            heavy_loads: dict[str,float] = {}
            # First pass: Compute PT and initial FT allocations
            for onu_id in group:
                Bmax = self.ONUs[onu_id].max_bw
                RT = self.ONUs[onu_id].get_RT()
                HCT = self.ONUs[onu_id].avg_HCT
                
                if RT[TCont.T1.value] != 0:
                    group_PT[onu_id] = {1: RT[TCont.T1.value], 2: 0, 3: 0, 4: 0}
                    group_FT[onu_id] = {1: Bmax, 2: 0, 3: 0, 4: 0}
                    continue
                
                # Compute Delta_PT
                Delta_PT: dict[TCont,int] = {}
                for t in [2,3,4]:
                    if t == TCont.T2.value:
                        Delta_PT[2] = 0
                    else:
                        Delta_PT[t] = RT[t] - HCT[t]
                # Compute PT
                PT: dict[TCont,int] = {1:0}
                for t in [2,3,4]:
                    PT[t] = RT[t] + Delta_PT[t]
                total_PT = sum(PT.values())
                group_PT[onu_id] = PT
                # Compute initial FT (First Value)
                FT: dict[int,float] = {1:0}
                Bmin_remaining = Bmax
                FT[2] = min(Bmin_remaining, PT[2])
                Bmin_remaining -= FT[2]
                FT[3] = min(Bmin_remaining, PT[3])
                Bmin_remaining -= FT[3]
                FT[4] = min(Bmin_remaining, PT[4])
                allocated_bw: float = sum(FT.values())
                group_FT[onu_id] = FT
                # Decide whether ONU is lightly loaded or heavily loaded
                if allocated_bw < Bmax:
                    # Lightly loaded ONU
                    group_Bexcess += Bmax - allocated_bw
                    lightly_loaded_onus.append(onu_id)
                elif total_PT > Bmax:
                    # Heavily loaded ONU
                    excess_demand = total_PT - Bmax
                    heavy_loads[onu_id] = excess_demand
                    heavily_loaded_onus.append(onu_id)
            # Redistribute Bexcess among heavily loaded ONUs
            total_heavy_load = sum(heavy_loads.values())
            if total_heavy_load > 0 and group_Bexcess > 0:
                for onu_id in heavily_loaded_onus:
                    # Calculate share of Bexcess
                    share = (heavy_loads[onu_id] / total_heavy_load) * group_Bexcess
                    PT = group_PT[onu_id]
                    FT = group_FT[onu_id]
                    # Distribute share among T-Conts
                    # Bexcess is first assigned to T-Cont 2, then 3, then 4
                    Bexcess_remaining = share
                    for t in [2,3,4]:
                        BW_needed = PT[t] - FT[t]
                        if BW_needed > 0:
                            alloc = min(Bexcess_remaining, BW_needed)
                            FT[t] += alloc
                            Bexcess_remaining -= alloc
                            if Bexcess_remaining <= 0:
                                break
                    group_FT[onu_id] = FT
            # Store allocations
            for onu_id in group:
                allocations[onu_id] = group_FT[onu_id]
        return allocations

    def remove_transmitted(self, allocations: dict[str,dict[int,float]]):
        for onu_id, allocation in allocations.items():
            onu = self.ONUs[onu_id]
            for t in [2,3,4]:
                allocated_bw = allocation[t]
                remaining_alloc = allocated_bw
                
                while onu.queue[t] and remaining_alloc > 0:
                    pkt = onu.queue[t][0]
                    if remaining_alloc >= pkt.size:
                        remaining_alloc -= pkt.size
                        onu.queue[t].pop(0)
                    else:
                        onu.queue[t][0].size -= remaining_alloc
                        remaining_alloc = 0
                        break

    def simulate_cycle(self):
        self.traffic_generator()
        allocations = self.DBA()
        # self.remove_transmitted(allocations)
        return allocations


def simulate():
    # Usage example
    
    ONUS = [
        ONU("ONU1", 10, 1.244e9, {1:0, 2:0.6, 3:0.2, 4:0.2}),
        ONU("ONU2", 10, 1.244e9, {1:0, 2:0.8, 3:0.0, 4:0.2}),
        ONU("ONU3", 10, 1.244e9, {1:0.2, 2:0.4, 3:0.2, 4:0.2}),
        ONU("ONU4", 10, 1.244e9, {1:0, 2:0.6, 3:0.2, 4:0.2}),
        ONU("ONU5", 10, 1.244e9, {1:0, 2:0.7, 3:0.2, 4:0.1}),
        ONU("ONU6", 10, 1.244e9, {1:0.4, 2:0.6, 3:0, 4:0}),
        ONU("ONU7", 10, 1.244e9, {1:0, 2:0.6, 3:0.4, 4:0}),
        ONU("ONU8", 10, 1.244e9, {1:0, 2:0.8, 3:0.2, 4:0})
    ]
    
    groups = [["ONU1", "ONU2"], ["ONU3", "ONU4"], ["ONU5", "ONU6"], ["ONU7", "ONU8"]]
    
    simulator = DBA_Simulator(ONUS, groups)

    print("Simulation for traffic proportions 60% T-Cont 2, 20% T-Cont 3, 20% T-Cont 4\n")
    for cycle in range(10):
        allocations = simulator.simulate_cycle()
        print(f"Cycle {cycle+1} allocations:")
        for onu_id, allocation in allocations.items():
            print(f"ONU {onu_id}: FT1: {allocation[1]:.2f}, FT2: {allocation[2]:.2f}, FT3: {allocation[3]:.2f}, FT4: {allocation[4]:.2f}")
        print("\n")

        
if __name__ == "__main__":
    simulate()