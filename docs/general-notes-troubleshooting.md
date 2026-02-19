# General Notes & Troubleshooting

This section outlines critical operational constraints, exchange-specific behaviours, and system resource management guidelines for the Hummingbot deployment.

# 1. Exchange-Specific Constraints

This section details the operational limitations, security requirements, and technical risks associated with specific exchange connectors.

## P2B Exchange: Ticker Visibility & Connectivity

### Ticker Visibility Issue

The P2B ticker endpoint automatically delists trading pairs from its public feed if the **bid-ask spread exceeds 1%**. If the spread widens beyond this threshold, Hummingbot will lose access to market data and trading rules, causing strategy execution to fail.

* **Resolution:** Immediately pause the bot and manually place orders on the exchange to tighten the spread below **1%**. Once the pair reappears in the ticker, restart the Hummingbot instance.

### Connectivity & IP Policy

* **Whitelisting:** P2B does **not** require IP whitelisting for its API.

* **Access:** You may execute requests from any IP address provided you possess valid API keys.

## Coinstore: Performance Limits & Strategic Risks

### Rate Limit Constraints

The observed API rate limits are significantly more restrictive than stated in the official documentation.

* **Threshold:** Maximum of about 3 **requests per second**.

* **Consequence:** Exceeding this limit triggers an HTTP 429 (Too Many Requests) error, resulting in an automatic **1-hour IP ban**.

* **Workaround:** If an IP is banned, you must wait for the lockout to expire or route traffic through a different whitelisted IP.

### Strategic Counter-Trading Risk

If the market spread reaches the **2% – 3%** range, external counter-trading bots often engage the order book. These bots can aggressively fill your orders, leading to unintended inventory imbalance or balance loss. **Maintain tight spreads to prevent predatory bot activity.**

### IP Whitelisting Requirements

**Warning:** Coinstore requires strict IP whitelisting for all API keys. Unauthorized IP addresses will result in connectivity and authentication errors.

* **Authorized Infrastructure:** Access is restricted to **Local Development Servers/office** (`<OFFICE_IP>`), **iWeb** (`<IWEB_PUBLIC_IP>`), and **AWS servers** (`<AWS_PROD_1_IP>`, `<AWS_PROD_2_IP>`) only.

## UZX: Security & Access Control

### IP Whitelisting Requirements

Similar to Coinstore, UZX enforces a rigorous IP security policy. You will encounter "IP not whitelisted" errors if attempting to connect from unauthorized networks.

* **Authorized Infrastructure**: Access is restricted to **Local Development Servers/office** (`<OFFICE_IP>`), **iWeb** (`<IWEB_PUBLIC_IP>`), and **AWS servers** (`<AWS_PROD_1_IP>`, `<AWS_PROD_2_IP>`) only.

* **Verification:** Ensure that the specific static IP of your instance is added to the UZX API key configuration before deployment.

### 2. System Resource Management

#### **Docker Instance Initialization**

Resource Usage:
Initializing a new Hummingbot Docker instance via the Dashboard consumes approximately 4 GB of RAM and triggers a significant CPU spike.

Stability Protocol:
launching multiple instances or building images simultaneously can exhaust server resources and cause a system crash.

* Procedure: Create instances sequentially.

* Wait Time: Allow a 5-minute buffer after starting an instance (until initialization is complete) before launching the next one or triggering a new build.

### 3. Build & Deployment Dependencies

#### **Custom CLI Integration**

The Hummingbot Dashboard Docker image relies on a custom version of the Hummingbot CLI.

* Requirement: The CLI is installed as a library from the local source code during the build process.

* Configuration: specific file paths to the local source code are correctly defined in your build configuration. This applies to both the Dashboard and the Backend API builds. Incorrect paths will cause the build to fail.
