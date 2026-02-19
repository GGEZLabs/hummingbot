# Memory Management

# SOP: Linux Memory Management & Docker Optimization

## 1. Objective

To prevent Out-Of-Memory (OOM) crashes on the host server by implementing system-level fail-safes (Swap) and container-level resource constraints.

## 2. System Analysis Tools

Before applying fixes, identify resource usage baselines.

* **Host Level:**
  * `htop`: Visual, real-time overview of CPU/RAM.
  * `free -h`: Check physical RAM vs. Swap usage.
  * `vmstat 1`: Monitor system paging (si/so columns) to check for "thrashing."
* **Docker Level:**
  * `docker stats`: Live stream of CPU, Memory, and Network I/O for all running containers.

## 3. System-Level Optimization (Swap Configuration)

Swap acts as an overflow buffer. Without it, the Linux kernel OOM Killer will terminate processes (often the database or Docker daemon) immediately when RAM is full.

### 3.1. Check Existing Swap

*`sudo swapon --show`*

*If the output is empty, no swap is configured.*

### 3.2. Create Swap File (Standard 4GB)

1. **Allocate the file:**

*`sudo fallocate -l 4G /swapfile`*

2. **Secure permissions (Critical)**

*`sudo chmod 600 /swapfile`*

3. **Initialize swap area:**
   *`sudo mkswap /swapfile`*
4. **Enable swap:**

*`sudo swapon /swapfile`*

5. **Persist Changes:**
   Add the following line to `/etc/fstab` to ensure swap loads on reboot:

*`echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab`*

### 3.3. Tune "Swappiness"

By default, Ubuntu sets swappiness to `60` (swaps aggressively). For servers, lower this to prevent disk I/O latency unless absolutely necessary.

1. **Check current value:** `cat /proc/sys/vm/swappiness`
2. **Set to 10 (Recommended for servers):**

*`sudo sysctl vm.swappiness=10`*

3. **Make permanent:**
   Edit `/etc/sysctl.conf` and add:

*`vm.swappiness=10`*

## 4. Docker-Level Optimization (Resource Limits)

Containers have no limits by default and can consume 100% of host RAM.

### 4.1. Hard Limits vs. Soft Limits

* **Hard Limit (`--memory` / `-m`):** The container is killed if it exceeds this.
* **Soft Limit (`--memory-reservation`):** Docker tries to keep usage below this, but allows spikes if the host has free RAM.

### 4.2. Option A: Limiting New Containers

When launching a container, define the maximum RAM allowed.

**Command:**

*`docker run -d --name my-app \`*

  *`--memory="2g" \`*

  *`--memory-swap="2g" \`*

  *`my-image:latest`*

**Note:** Setting `--memory-swap` to the same value as `--memory` effectively disables swap *for that specific container*, forcing it to stay strictly within physical RAM or be killed.

### 4.3. Option B: Updating Running Containers

If a container is already running and cannot be recreated (e.g., maintaining state), update its limits dynamically.

**Command:**

*`# Syntax: docker update --memory <limit> --memory-swap <limit> <container_id>`*

*`docker update --memory 2g --memory-swap 2g 132bbe2abce6`*

### 4.4. Option C: Docker Compose (Recommended)

Define limits in `docker-compose.yml` for infrastructure-as-code.

*`services:`*

  *`app:`*

    *`image: my-app`*

    *`deploy:`*

      *`resources:`*

        *`limits:`*

          *`memory: 2G`*

        *`reservations:`*

          *`memory: 1G`*

## 5. Maintenance Commands

Periodically clean up unused resources to free up overhead.

* **Prune stopped containers and unused networks:**

*`docker system prune -f`*

* **Sort containers by memory usage:**

*`docker stats --format "table {{.Name}}\t{{.MemUsage}}" --no-stream`*
