# Development & Deployment Workflow

This guide outlines the end-to-end process for developing strategies, testing code changes, and deploying updates to the live production environment.

## 1. Local Development Cycle

### Step 1: Strategy & Connector Development

* Develop: Write or modify your strategy or connector code within the local source directory.

* Debug: Execute the Hummingbot CLI from source code in debug mode to verify logic and catch errors in real-time.

* Verify: Ensure all functionality works as expected in the local CLI environment before proceeding.

make sure you have a valid API Key for the needed connector

### Step 2: Synchronization

To ensure consistency across the ecosystem, any changes to scripts or controllers must be propagated to the hummingbot-backend-api and hummingbot-deploy repository.

**Action**: Copy updated files from the CLI source to the target directories.

* **Source:**
  * `~/hummingbot/scripts`
  * `~/hummingbot/controllers`
* **Destinations:**
  * **Deploy:** `~/hummingbot-deploy/bots/scripts` & `~/hummingbot-deploy/bots/controllers`
  * **Backend API:** `~/hummingbot-backend-api/bots/scripts` & `~/hummingbot-backend-api/bots/controllers`

### Step 3: Full System Integration Test

1. **Update Core Library (If Applicable):**
   If you have modified core logic within \~/hummingbot/hummingbot (such as controllers, data\_feed, or other core modules), you must reinstall the Hummingbot CLI package as a library in your development environment to apply the changes.
   *conda activate \[environment\_name\]*

   *pip install ../hummingbot*

2. **Run Components:**
   Launch the Backend API and Dashboard services locally.
3. **Build Local Docker Image:**
   To test the integration with the Dashboard, you must build a local Docker image of your modified Hummingbot CLI. The Dashboard uses this image to spawn bot instances.
4. **Deploy Instance:**
   Create and launch a Hummingbot instance via the local Dashboard interface to verify the full operational cycle (creation, configuration, and execution).

## 2. Build & Release Process

### Step 1: Commit & Pull

1. **Commit**: Commit your finalized code changes to the version control system.

2. **Access Build Server**: SSH into your local build server.

3. **Pull**: Pull the latest changes from the repository.

### Step 2: Docker Image Construction

1. **Verify Config:** Check the docker-compose.yml file to confirm the correct image names and tags are specified.
2. **Build:** Execute the build command:

*`docker compose build`*

### Step 3: Push to ECR

Upload the newly built images to the Amazon Elastic Container Registry (ECR).

* **Authentication:** If your session has expired, re-authenticate Docker with ECR (Public):

*aws ecr-public get-login-password \--region us-east-1 | docker login \--username AWS \--password-stdin public.ecr.aws*

* **Push:** Push the images to the repository.

*`docker compose push`*

## 3. Production Deployment

### Step 1: Update Live Servers

1. **Access Live Server:** SSH into the production server.
2. **Sync Files:** Pull the latest repository changes, ensuring the bots/ folder is updated with the latest scripts and controllers.
3. **Pull Images:** Download the new Docker images from ECR.

### Step 2: Clean & Redeploy

1. **Cleanup:**
   * Stop and remove old containers.
   * Remove old images to free up space.
   * Delete obsolete instance configurations: rm \-rf bots/instances/\[instance\_name\]
2. **Launch:**
   Start the updated stack:

*docker compose up \-d*

### Step 3: Final Verification

1. Access the live Dashboard.
2. Create and launch new Hummingbot instances.
3. Verify that all bots are running the latest strategy versions correctly.
