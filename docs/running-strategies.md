# Running Strategies

| Developed strategies |  |  |
| ----- | :---- | :---- |
| **Streategy** | **Type** | **Description**  |
| Volume Pumper | Controller | Generates trading volume on CEXs by creating matched buy/sell order pairs every X amount of time |
| Random Transactions  | Script | Generates send transactions on the chain using GRPC between the provided accounts every X amount of time |
| Volume monitor | Script | Monitor the trading volume for the provided CEXs, and notify the user when an exchange's trading volume is below a threshold  |
| Dex Volume Pumper | script | Generate trades(swaps) on DEXs every X amount of time |
| Two Accounts Volume Pumper | script | Generates trading volume on CEXs by creating matched buy/sell order pairs every X amount of time, using 2 MM accounts  ( OUTDATED / NEED REVIEW )  |

## Hummingbot Script & Controller Management Guide

This guide details the procedures for configuring, running, and deploying Hummingbot scripts and controllers using the CLI and the Dashboard.

### Part 1: CLI Operations

### 1. Configure Connectors

Before running strategies, ensure your exchange connectors are authenticated.

1. **Run the connect command:**

*`connect [connector_name]`*

2. **Enter Credentials:**
   Follow the prompts to input your `api-key` and `secret-key`.

### 2. Create Configuration Files

**For Standard Scripts**

To generate a configuration file for a Python script:

1. Run the creation command:

*`create --script-config [script_name]`*

2. Follow the prompts to populate the configuration parameters.
3. **File Location:** The config file is saved to:
   `~/hummingbot/conf/scripts/[script_config_filename]`

**For V2 Controllers**

To generate a configuration for a strategy controller:

1. Run the creation command:
   *`create --controller-config [controller_name]`*
2. Follow the prompts to populate the controller parameters.
3. **File Location:** The config file is saved to:
   `~/hummingbot/conf/controllers/[controller_config_filename]`

**For V2 Controller Runners**

To run a controller, you must create a configuration for the `v2_with_controllers` runner script:

1. Run the command:

*`create --script-config v2_with_controllers`*

2. **Link Controller:** When prompted to "Enter controller configurations...", input the filename of your saved controller config (e.g., `my_controller_conf.yml`).
3. **File Location:** The runner config is saved to:
   `~/hummingbot/conf/scripts/[v2_runner_config_filename]`

### 3. Execution

* **To Run a Standard Script:**

*`start --script [script_name] --conf [script_config_filename]`*

* **To Run a V2 Controller:**
  Execute the V2 runner script pointing to your runner config:

*`start --script v2_with_controllers.py --conf [v2_runner_config_filename]`*

## Part 2: Dashboard Deployment

### 1. Environment Synchronization

To ensure consistent deployment, scripts and controllers must be synchronized across the `bots` folders of all Hummingbot components (CLI, Backend API, and Deploy).

**Action:** Copy any updated files from your CLI directory to the Backend and Deploy directories.

* **Source:**
  * `~/hummingbot/scripts`
  * `~/hummingbot/controllers`
* **Destinations:**
  * `~/hummingbot-deploy/bots/scripts` & `~/hummingbot-deploy/bots/controllers`

  * `~/hummingbot-backend-api/bots/scripts` & `~/hummingbot-backend-api/bots/controllers`

### 2. Credentials & Account Management

Navigate to the **Credentials** page on the Dashboard.

* **Master Account:** Ensure the default account is present as `master_account`.
* **Add Keys:** Add the API and Secret keys for the required connectors.
* **Accounts Configuration:** You can create, update, or delete Hummingbot CLI configurations here. This allows multiple bots to run on the same account using different CLI settings.

### 3. Creating Configurations in Dashboard

Navigate to the **Script/Controller Config** page.

* Use the interface to generate new configuration files for your strategies.
* **Save Locations:**
  * Controllers: `~/bots/conf/controllers/[filename]`
  * Scripts: `~/bots/conf/scripts/[filename]`

### 4. Deploying V2 Instances

Navigate to the **Deploy V2** page to launch a bot.

1. **Instance Name:** Enter a unique name for the instance.
2. **Credentials Profile:** Select the account (e.g., `master_account`).
3. **Credentials Profile Config:** Select the specific CLI config to use.
4. **Hummingbot Image:** Select the Docker image (must be installed on the Same server).
5. **Headless Mode:** to Run Hummingbot in Headless Mode, check the switch (Default: True).
6. **Select Strategy:**
   * Choose the **Controllers** or **Scripts** tab.
   * Select the specific configuration file you created.
7. **Launch:** Click **Run**.

### 5. Instance Architecture

Upon launch, a directory is created at `~/bots/instances/[Instance_Name_timestamp]`. This folder contains all necessary volumes for the Docker container:

* **Core Configs:**`/config/conf_client.yml`, `/config/conf_fee_overrides.yml`, `/config/hummingbot_logs.yml`
* **Subdirectories:**
  * `/config/connectors`
  * `/config/controllers`
  * `/config/scripts`

### 6. Monitoring & Management

Navigate to the **Instances** page to view running bots.

* **Actions:** You can stop the Docker instance, stop the controller (while keeping the container running), and view logs/errors.

**Known Issue:**
If a Docker instance is running a **Script** (rather than a Controller), the status may display as **"Stopped"**. The current system status check looks specifically for active controllers. Verify script activity via the logs if the status appears incorrect.
