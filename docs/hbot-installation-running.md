# HBot Installation & Running

# Required Dependencies

* ### build-essentials , curl and git

  ## *sudo apt update && sudo apt upgrade \-y && sudo apt install \-y build-essential && sudo apt  install curl &&* *sudo apt install git-all*

* ### Miniconda

  ## *curl \-O* [https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86\_64.sh](https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh)

## 	 	*bash \~/Miniconda3-latest-Linux-x86\_64.sh*

1. Enter yes to agree to the license agreement
   2. Enter yes to accept the default install location
   3. Enter yes to  initialize conda whenever you open a new shell
   4. Close and re-open your terminal window for the installation to fully take effect, or use the following command to refresh the terminal

   *source \~/.bashrc*

* ### Docker (required for Hummingbot dashboard or running production build)

       using install-using-the-repository from [Docker docs](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository)   run the following commands :

1. Set up Docker's apt repository.
   *\# Add Docker's official GPG key:*

   *sudo apt-get update*

   *sudo apt-get install ca-certificates curl*

   *sudo install \-m 0755 \-d /etc/apt/keyrings*

   *sudo curl \-fsSL https://download.docker.com/linux/ubuntu/gpg \-o /etc/apt/keyrings/docker.asc*

   *sudo chmod a+r /etc/apt/keyrings/docker.asc*

   *\# Add the repository to Apt sources:*

   *echo \\*

     *"deb \[arch=$(dpkg \--print-architecture) signed-by=/etc/apt/keyrings/docker.asc\] https://download.docker.com/linux/ubuntu \\*

     *$(. /etc/os-release && echo "$VERSION\_CODENAME") stable" | \\*

    	*sudo tee /etc/apt/sources.list.d/docker.list \> /dev/null*

   *sudo apt-get update*

2. Install the Docker packages.

   *sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin*

3. Gaining permission (if facing a permission error)

   The Docker daemon requires root privileges, but you can grant access to non-root users by adding them to the docker group by running this command:

   *sudo usermod \-aG docker $USER*

		Log out and back in to apply the group changes.

# Installing the Hummingbot CLI

## Install Hummingbot (source)

Run the following commands to install Hummingbot from source:

* Installing source code
  *git clone https://github.com/GGEZLabs/hummingbot.git*

  *cd hummingbot*

* Check out the Hbot 2.7 branch (**Optional**)
  *git checkout  v-2.7.0*

* Installing dependencies (**Required only for source launch**)
  *./install*

  *conda activate hummingbot*

  *./compile*

# Launch Hummingbot (source)

Inside the **hummingbot** folder, activate the hummingbot conda environment if not already by running this command:
*conda activate hummingbot*

The conda activate hummingbot command should add a (hummingbot) label in front of your command line, which lets you know that you are inside the conda environment

Run the following command to launch Hummingbot:

*./start*

# Launch Hummingbot (Docker)

1. ## Auto start containers with a preconfigured strategy

   To auto-run a preconfigured strategy for each instance,  in docker-compose.yml file, edit or add  the section that defines the environment variables:

     environment:

       \- CONFIG\_PASSWORD=**\<password\>**

       \- CONFIG\_FILE\_NAME=**\<strategy\_file\>**

       \- SCRIPT\_CONFIG=**\<strategy\_config\_file\>**

   Check the hummingbot documentation for more details

   [https://hummingbot.org/global-configs/strategy-autostart/\#how-to-autostart](https://hummingbot.org/global-configs/strategy-autostart/#how-to-autostart)

2. ## To run the Hummingbot in a Docker container, use :

   *docker compose up \-d*

# Launch Hummingbot (Debug Mode Using VSCode)

1. ## Create a launch.json file

   1. ### Navigate to the "hummingbot/.vscode/" directory.

   2. Create a file named launch.json with the following content:
      *{*

        *"version": "0.2.0",*

        *"configurations": \[*

          *{*

            *"name": "Python: Hummingbot Quickstart Debug",*

            *"type": "debugpy",*

            *"request": "launch",*

            *"program": "${workspaceRoot}/bin/hummingbot\_quickstart.py",*

            *"console": "integratedTerminal",*

            *"python": \<path\_to\_conda\_environment\>* *,*

            *"args": \[*

              *// "--headless", // for running the CLI in Headless mode*

              *// "-p", // taking the password as argument*

              *// "a" // the actual password*

              *// "-f", "volume\_monitor.py", // the starting strategy file*

              *// "-c", "conf\_volume\_monitor\_1.yml" // starting strategy config file*

            *\]*

          *}*

        *\]*

      *}*

2. Set the Python environment path
   1. Open a terminal and activate the Hummingbot conda environment:

   *conda activate hummingbot*

   2. Get the Python executable path:
      *which python*

   3. Copy the output path and replace *\<path\_to\_conda\_environment\>* in the launch.json file with it.
3. Run Hummingbot in debug mode
   1. In **VSCode**, go to the Run & Debug tab.
   2. Select the configuration named "**Hummingbot Application**".
   3. Press **F5** (or click Run).

Hummingbot will now launch in debug mode with breakpoints enabled.

# Installing Hummingbot Dashboard v-2.2.0 (Docker build)

1. ## Creating The Hummingbot CLI Docker Image

* ### Cloning the humming bot files from **ggez-labs** repo

  *git clone https://github.com/GGEZLabs/hummingbot.git*

  *cd hummingbot*

* ### Building the Humming bot image

  *docker compose up \--build \--no-start*

  *or*

  *docker compose build*

2. ## Creating The Backend Api Docker Image

* ### Cloning the humming bot back end api files from **ggez-labs** repo

  *git clone https://github.com/GGEZLabs/hummingbot-backend-api.git*

  *cd hummingbot-backend-api*

* ### Setting up .env file

  *bash set\_environment.sh*

* ### Building the Humming bot image

  *docker compose up \--build \--no-start*

3. ## Creating The Dashboard Docker Image

* Cloning the humming bot  files dashboard from **ggez-labs** repo

  *git clone https://github.com/GGEZLabs/hummingbot-dashboard.git*

  *cd hummingbot-dashboard*

* ### Building the Humming bot image

  *docker compose up \--build \--no-start*

4. ## Creating Shared Network for docker images

* Creating docker shared-network

  *docker network create shared-network*

# Installing Hummingbot Dashboard v-2.7.0 (Docker build)

In the same folder, do the following commands

1. ## Creating The Hummingbot CLI Docker Image

* ### Cloning the humming bot files from **ggez-labs** repo

  *git clone https://github.com/GGEZLabs/hummingbot.git*

  *cd hummingbot*

  *git checkout  v-2.7.0*

* ### Build or pull Hummingbot image

  * ### Building the Hummingbot image

    *docker compose build*

* ### Pulling ECR image

  *docker compose pull*

2. ## Creating The Backend Api Docker Image

* ### Cloning the humming bot back end api files from **ggez-labs** repo

  *git clone https://github.com/GGEZLabs/hummingbot-backend-api.git*

  *cd hummingbot-backend-api*

  *git checkout  v-2.7.0*

* ### Setting up .env file

  *bash [setup.sh](http://setup.sh)*

* ### Update database connection the backend api need to connect to a postgresql database

  Open docker-compose.yml  in the hummingbot-ap service

  update the DATABASE\_URL , DATABASE\_SCHEMA environment variables with correct values

* ### Building the Humming bot backend api image

  *docker compose build*

3. ## Installing the Backend Api Client package

* ### Cloning the humming bot back-end api client files from **ggez-labs** repo

  *git clone https://github.com/GGEZLabs/hummingbot-api-client*

4. ## Creating The Dashboard Docker Image

* Cloning the humming bot  files dashboard from **ggez-labs** repo
  *git clone https://github.com/GGEZLabs/hummingbot-dashboard.git*

  *cd hummingbot-dashboard*

  *git checkout  v-2.7.0*


* ### Building the Humming bot image

  *docker compose build*

5. ## Creating Shared Network for docker images

* Creating docker shared-network
  *docker network create shared-network*

# Launch Hummingbot Dashboard v-2.7.0 (source)

	launching Hummingbot Dashboard v-2.7.0  using the source code you need to have the humminbot 2.7 source code and hummingbot-api-client source code

1. Launching Hummingbot Dashboard

   Inside the **hummingbot Dashboard** folder

   Run the following commands to install Hummingbot from source:

    run this command:

* Check out the 2.7 branch

  *git checkout  v-2.7.0*

* Installing dependencies

  *./install*

  *conda activate dashboard*

  *pip install \<path to humminbot 2.7 source code\>*

  *pip install \<path to hummingbot-api-client source code\>*


* Run the following command to launch Hummingbot:

  *make run*


2. launching Hummingbot Backend API

   run this command:

* Check out the 2.7 branch

  *git checkout  v-2.7.0*

* Installing dependencies

  *./install*

  *conda activate hummingbot-api*

  *pip install \<path to humminbot 2.7 source code\>*

* Run the following command to launch Hummingbot:

  *make run*


# Launch Hummingbot Dashboard (Docker)

1. ## Starting Hummingbot Backend Api

   Inside the **hummingbot-backend-api** folder  run:

   *docker compose up \-d*

2. ## Starting Hummingbot Dashboard

		Inside the **hummingbot-dashboard** folder  run:

*docker compose up \-d*

# Installing Hummingbot Gateway v-2.2.0

1. ## Creating The Hummingbot Gateway Docker Image

   In the same folder :

* ### Cloning the humming bot files from **ggez-labs** repo

  *git clone https://github.com/GGEZLabs/hummingbot.git*

  *cd hummingbot*

* ### Cloning the humming gateway files from **ggez-labs** repo

  *git clone https://github.com/GGEZLabs/hummingbot-gateway.git*

  *cd hummingbot-gateway*

* ### Building the gateway image

  In the hummingbot folder

  Uncomment the gateway service  in docker-compose.yml file

  Run :

  *docker compose build*

# Install and launch Hummingbot Dashboard using Deploy repo

1. ## Clone the Repository

   run:

   *git clone https://github.com/GGEZLabs/hummingbot-deploy.git*

   *cd hummingbot-deploy*

2. ## Run the Setup Script

   Execute the setup script to download Docker images:

   *bash setup.sh*

   this setup command does this :​

   1. Pulls all required Docker images from docker-compose.yml
   2. Creates a .env file with default configuration (CONFIG\_PASSWORD=a)
   3. Sets the bots path to the current directory
   4. Starts all services using Docker Compose

3. ## Validate Configuration

Before launching, ensure the following files were created or populated correctly in your directory:

1. .env: Check that environment variables
   1. Make sure variables like CONFIG\_PASSWORD,DATABASE\_URL, DATABASE\_USED\_SCHEMA are set correctly.
2. docker-compose.yml: Verify volume mappings and port definitions.
   1. credentials.yml file, the bots folder is not the same for all servers (aws servers use the shared folder *"/shared-efs/bots/"*)
3. Enable Authentication For Dashboard
   1. Open hummingbot-deploy/credentials.yml file
   2. Modify the username and password to the desired values
   3. Enable Authentication in Docker Compose buy Change the value of AUTH\_SYSTEM\_ENABLED flag to True

4. ## Run Containers

   Launch the application services in detached mode:

   *docker compose up \-d*

# Installing Hummingbot Gateway v-2.7.0

2. ## Creating The Hummingbot Gateway Docker Image

   In the same folder :

* ### Cloning the humming bot files from **ggez-labs** repo

  *git clone https://github.com/GGEZLabs/hummingbot.git*

  *cd hummingbot*

  *git checkout  v-2.7.0*

* ### Cloning the humming gateway files from **ggez-labs** repo

  *git clone https://github.com/GGEZLabs/hummingbot-gateway.git*

  *cd hummingbot-gateway*

  *git checkout  v-2.7.0*

* ### Building the gateway image

  In the hummingbot folder

  Uncomment the gateway service  in docker-compose.yml file

  Run :

  *docker compose build*

# Connecting Hummingbot with Gateway

1. ## Start the Hummingbot container

   ##     *docker compose up \-d*

   ### *docker attach hummingbot*

2. ### Generate Gateway SSL certificates inside Hummingbot

   Ensure the `certs_path` in hummingbot/conf/conf\_client.yml is set to:
    	*certs\_path: /home/hummingbot/certs*

   Run the following command inside the Hummingbot terminal:
   	*gateway generate\_certs*

   * When prompted:

     * Enter the passphrase to generate Gateway SSL certificates.

       * **Important:** Use the same passphrase as `GATEWAY_PASSPHRASE` in your hummingbot/docker-compose.yml file.

3. ### Stop all containers      *docker compose down*

4. ### Run the Gateway setup script

   From the `hummingbot-gateway` folder, execute:
   	*./gateway-setup.sh*

* When prompted:
  *  `Do you want to copy over client certificates (Y/N) >>> Y`
  * `Enter path to the Hummingbot certs folder >>> <Path_to_hummingbot_folder>/hummingbot/certs`

5. ### Restart the containers

		*docker compose down*

*docker compose up \-d*

### *docker attach hummingbot*

6. ### Verify Gateway integration

   1. When Hummingbot starts, it should detect and connect to Gateway automatically.

      On first run, Hummingbot will create the folder:
       `hummingbot/gateway_files/conf/`

   2. ### Configure blockchain connection ( Required only when using gateway  v-2.7.0 )

      1. Open `hummingbot/gateway_files/conf/solana.yml`
      2. Replace `<quiknode_token>` with your actual QuikNode token.

7. ### Restart the containers

		*docker compose down*

*docker compose up \-d*

### *docker attach hummingbot*
