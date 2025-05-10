import os
import builtins
import random
import simpy
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import csv


# Ensure output directory exists
if not os.path.exists("output"):
    os.makedirs("output")

# Delete previous output files if they exist
for filename in ["output/output.txt", "output/output.png", "output/network_summary.csv", "output/network_coordinates.csv"]:
    if os.path.exists(filename):
        os.remove(filename)

# Logging function with UTF-8 encoding
def log(*args, **kwargs):
    with open("output/output.txt", 'a', encoding='utf-8') as f:
        builtins.print(*args, **kwargs, file=f)
    builtins.print(*args, **kwargs)

# Config input
def configure_simulation():
    print("Using default simulation parameters")
    config = {
        "RANDOM_SEED": 1111,
        "NUM_NODES": 50,
        "AREA_WIDTH": 125,
        "AREA_HEIGHT": 125,
        "MINIMUM_DISTANCE": 5,
        "CONNECTION_RANGE": 15,
        "DIO_INTERVAL": 10,
        "NODE_CREATION_INTERVAL": 1,
        "RUNTIME": 120
    }
    try:
        configure = input("Do you want to configure simulation parameters? y/[N]: ")
        if configure.lower() == 'y':
            for key in config:
                val = input(f"Enter {key.replace('_', ' ').title()} [{config[key]}]: ")
                config[key] = int(val) if val else config[key]
    except (ValueError, KeyboardInterrupt):
        print("Invalid input or operation cancelled. Proceeding with default parameters.")
    return config

config = configure_simulation()
random.seed(config["RANDOM_SEED"])

class Node:
    def __init__(self, env, node_id, position, all_nodes):
        self.env = env
        self.node_id = node_id
        self.position = position
        self.all_nodes = all_nodes
        self.neighbors = []
        self.parent = None
        self.prefix = f'2001:db8::{int(node_id[4:]):02x}'
        self.Imin = 1
        self.Imax = 10
        self.I = self.Imin
        self.t = random.uniform(self.Imin, self.I)
        self.rank = random.randint(1, 10)
        self.color = (random.random(), random.random(), random.random())

    def discover_neighbors(self):
        yield self.env.timeout(0.1)
        for node in self.all_nodes:
            if node != self and self.calculate_distance(node.position) <= config["CONNECTION_RANGE"]:
                self.env.process(node.receive_dis(self))

    def send_dio(self):
        while True:
            for neighbor in self.neighbors:
                if neighbor.parent != self:
                    self.env.process(neighbor.receive_dio(self))
            yield self.env.timeout(config["DIO_INTERVAL"])

    def receive_dio(self, sender):
        if f':{int(self.node_id[4:]):02x}' in sender.prefix:
            return
        if not self.parent or self.calculate_distance(sender.position) < self.calculate_distance(self.parent.position):
            self.parent = sender
            self.prefix = f'{sender.prefix}:{int(self.node_id[4:]):02x}'
            yield self.env.process(self.send_dao())
        yield self.env.timeout(0)

    def send_dis(self):
        if not self.neighbors:
            for node in self.all_nodes:
                if node != self and self.calculate_distance(node.position) <= config["CONNECTION_RANGE"]:
                    self.env.process(node.receive_dis(self))
        yield self.env.timeout(0)

    def receive_dis(self, sender):
        if sender not in self.neighbors:
            self.neighbors.append(sender)
            sender.neighbors.append(self)
            self.env.process(sender.receive_dio(self))
        yield self.env.timeout(0.1)

    def send_dao(self):
        if self.parent:
            yield self.env.process(self.parent.receive_dao(self.prefix, self))

    def receive_dao(self, prefix, child):
        if f':{int(child.node_id[4:]):02x}' in prefix:
            return
        if self.parent:
            self.env.process(self.parent.receive_dao(prefix, self))
        yield self.env.timeout(0)

    def calculate_distance(self, other):
        return ((self.position[0] - other[0])**2 + (self.position[1] - other[1])**2)**0.5

    def trickle_timer(self):
        while True:
            yield self.env.timeout(self.t)
            if not self.neighbors:
                yield self.env.process(self.send_dis())
            self.I = min(self.I * 2, self.Imax)
            self.t = random.uniform(self.I, self.Imax)

def plot_network(nodes):
    fig, ax = plt.subplots(figsize=(12, 12))
    for node in nodes:
        x, y = node.position
        ax.scatter(x, y, color=node.color, s=120, zorder=3)
        ax.text(x, y + 2, f"{node.node_id}", fontsize=8, ha='center', weight='bold')
        ax.text(x, y - 2, f"ETX: {node.rank}", fontsize=7, ha='center', color='black')
        if not node.parent:
            ax.scatter(x, y, facecolors='none', edgecolors='red', linewidths=2, s=250, zorder=4)
            ax.text(x, y + 5, "Root", fontsize=9, ha='center', color='red')
    for node in nodes:
        if node.parent:
            x1, y1 = node.position
            x2, y2 = node.parent.position
            ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", color='gray', lw=1), zorder=2)
    ax.set_xlabel("Width (meters)")
    ax.set_ylabel("Height (meters)")
    ax.set_title("Node Distribution in RPL Simulation")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("output/output.png")
    plt.show()

def main():
    env = simpy.Environment()
    all_nodes = []
    for i in range(config["NUM_NODES"]):
        pos = (random.randint(0, config["AREA_WIDTH"]), random.randint(0, config["AREA_HEIGHT"]))
        node = Node(env, f"Node{i:02d}", pos, all_nodes)
        all_nodes.append(node)
        env.process(node.trickle_timer())
        env.process(node.discover_neighbors())
        env.process(node.send_dio())
    env.run(until=config["RUNTIME"])

    log("\n=== Parent-Child Relationships ===")
    root_count = 0
    for node in all_nodes:
        if node.parent:
            log(f"{node.node_id} -> {node.parent.node_id} (Prefix: {node.prefix})")
        else:
            log(f"{node.node_id} has no parent (ROOT)")
            root_count += 1

    log("\n=== Disconnected Nodes ===")
    disconnected = [n for n in all_nodes if not n.neighbors]
    if disconnected:
        for node in disconnected:
            log(f"{node.node_id} at position {node.position} is disconnected")
    else:
        log("None")

    total = len(all_nodes)
    connected = total - len(disconnected)
    log("\n=== Summary ===")
    log(f"Total nodes           : {total}")
    log(f"Connected nodes       : {connected}")
    log(f"Disconnected nodes    : {len(disconnected)}")
    log(f"Root nodes (no parent): {root_count}")

    with open("output/network_summary.csv", mode="w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Node ID", "Parent", "Prefix", "Is Root", "Is Disconnected", "Position", "Neighbors"])
        for node in all_nodes:
            writer.writerow([
                node.node_id,
                node.parent.node_id if node.parent else "None",
                node.prefix,
                not node.parent,
                not node.neighbors,
                node.position,
                ", ".join(n.node_id for n in node.neighbors)
            ])

    with open("output/network_coordinates.csv", mode="w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Node ID", "X", "Y", "Parent ID", "Parent X", "Parent Y"])
        for node in all_nodes:
            x, y = node.position
            if node.parent:
                px, py = node.parent.position
                writer.writerow([node.node_id, x, y, node.parent.node_id, px, py])
            else:
                writer.writerow([node.node_id, x, y, "", "", ""])

    plot_network(all_nodes)

main()
