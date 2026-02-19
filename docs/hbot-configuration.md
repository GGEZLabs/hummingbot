# HBot Configuration

the cli config file: hummingbot/conf/conf\_client.yml

Change the following keys with the recommended data

1. ## market\_data\_collection:

* ### market\_data\_collection\_enabled

  **Description**: Enable/disable the Market Data Collection feature.

  **Recommended**: true

* ### market\_data\_collection\_interval

  **Description:** Set the market data collection interval in seconds.

  **Recommended**: 60

* ### market\_data\_collection\_depth

  **Description:** Set the order book collection depth.

  **Recommended**: 2

2. ## rate\_oracle\_source:

* ### name:

  **Description**: The source where you want to pull token price data from.

  **Recommended**:  "GGEZ1"  token only available with p2b , uzx or coinstore, use the same exchange as in the running strategy.

3. ## certs\_path:

   **Description**: path to the certs folder

   **Recommended**:

   If the Hummingbot is running using:

* ### Docker:

  **should use**  "/home/hummingbot/certs"

* ### Source:

    	**should use** the actual path to "cert" folder


4. ## db\_mode:

   The database used to store orders, controllers state and market data, Configuration Parameters:

* ### db\_engine

  **allowed values**: sqlite,postgresql,mysql,oracle,mssql

* ### db\_host

  **allowed values**: any string e.g. 127.0.0.1

* ### db\_port

  **allowed values**: any string e.g. 3306

* ### db\_username

  **allowed values**: any string e.g. username

* ### db\_password

  **allowed values**: any string e.g. password

  **Notes:**

  * If the password contain "@"
    replace @ with %40

* ### db\_name

  **allowed values**: any string e.g. dbname

* ### db\_schema ( for Postgres databases)

		**allowed values**: any string e.g. market

5. ## telegram\_mode

   1. ## HBot 2.2

   	Create a Telegram bot, add it to a group chat, or start a private chat with it.

      Refer to this documentation ( [https://hummingbot.org/installation/hummingbot-api/\#telegram-optional](https://hummingbot.org/installation/hummingbot-api/#telegram-optional) ) to create a Telegram bot and get the chat ID

      Configuration Parameters:

* ### telegram\_token

  Enter the Telegram Bot  token ID

* ### telegram\_chat\_id

  Enter the chat ID

  2. ## HBot 2.7

  	Create a Telegram bot, add it to a group chat, or start a private chat with it.

     Refer to this documentation ( [https://hummingbot.org/installation/hummingbot-api/\#telegram-optional](https://hummingbot.org/installation/hummingbot-api/#telegram-optional) ) to create a Telegram bot and get the chat ID

     Configuration Parameters, Under telegram\_mode field set :

* ### telegram\_mode\_enabled

  Set it true

* ### telegram\_mode\_token

  Enter the Telegram Bot  token ID

* ### telegram\_mode\_chat\_id

  Enter the chat ID
