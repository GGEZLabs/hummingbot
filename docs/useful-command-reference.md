# Useful Command Reference

## 1. Docker Compose (Orchestration)

Used for managing multi-container applications defined in docker-compose.yml.

| Command | Description |
| :---- | :---- |
| ***docker compose up \-d*** | Builds, (re)creates, starts, and attaches to containers for a service. The \-d flag runs containers in the background (detached mode). |
| ***docker compose down*** | Stops and removes containers, networks, images, and volumes defined in the configuration file. |
| ***docker compose pull*** | Pulls the latest version of the images defined in docker-compose.yml from the registry without starting them. |
| ***docker compose push*** | Pushes the images defined in docker-compose.yml to the configured registry (e.g., ECR). |
| ***docker compose build*** | Builds or rebuilds services. Use this after changing code that requires a new image build. |

## 2. General Docker CLI

Used for managing individual images, containers, and system resources.

### Container Management

| Command | Description |
| :---- | :---- |
| ***docker ps \-a*** | Lists all containers, including those that are stopped or exited. |
| ***docker start \[container\]*** | Starts one or more stopped containers. |
| ***docker stop \[container\]*** | Stops one or more running containers gracefully. |
| ***docker restart \[container\]*** | Stops and then starts a container. Useful for applying configuration changes. |
| ***docker rm \[container\]*** | Removes one or more stopped containers. You must stop a container before removing it (unless using \-f). |
| ***docker stats*** | Displays a live stream of container resource usage statistics (CPU, memory, network I/O). |

### Image Management

| Command | Description |
| :---- | :---- |
| ***docker images*** | Lists all top-level images available locally on the system. |
| ***docker pull \[image\]*** | Downloads a specific image from a registry. |
| ***docker push \[image\]:\[tag\]*** | Uploads an image (with a specific tag) to a registry. |
| ***docker tag \[source\] \[target\]*** | Creates a tag target\_image that refers to source\_image. Essential for versioning before pushing to ECR. |
| ***docker rmi \[image\]*** | Removes one or more images. Fails if a container is currently using the image. |

### System Cleanup & Maintenance

| Command | Description |
| :---- | :---- |
| ***docker system prune \-f*** | Removes all unused containers, networks, and images (dangling). The \-f flag forces the action without a confirmation prompt. |
| ***docker builder prune \-a*** | Cleans up the build cache. The \-a flag removes all build cache, not just dangling ones. Useful for freeing up disk space after multiple builds. |

## 3. Environment Management (Conda & Pip)

Used for managing Python environments and dependencies during local development.

| Command | Description |
| :---- | :---- |
| ***conda env list*** | Lists all available Conda environments on the local machine. |
| ***conda activate \[env\_name\]*** | Switches the current shell session to the specified Conda environment. |
| ***conda deactivate*** | Deactivates the current Conda environment and returns to the base shell. |
| ***pip list*** | Lists all installed Python packages in the currently active environment. |
| ***pip install .*** | Installs the package in the current directory (used for installing Hummingbot as a library). |
