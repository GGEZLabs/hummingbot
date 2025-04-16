if [ -z "$1" ]; then
  echo "Error: No instance name provided." >&2 # Print error to standard error
  echo "Usage: sudo $0 <instance_name>" >&2
  exit 1 # Exit with a non-zero status to indicate failure
fi

INSTANCE_NAME="$1"

sudo mkdir -p conf/$INSTANCE_NAME/connectors/
sudo cp -r conf/connectors/* "conf/$INSTANCE_NAME/connectors/"
sudo mkdir -p conf/$INSTANCE_NAME/strategies/
sudo cp -r conf/strategies/* "conf/$INSTANCE_NAME/strategies/"
sudo mkdir -p conf/$INSTANCE_NAME/scripts/
sudo cp -r conf/scripts/* "conf/$INSTANCE_NAME/scripts/"
sudo mkdir -p conf/$INSTANCE_NAME/controllers/
sudo cp -r conf/controllers/* "conf/$INSTANCE_NAME/controllers/"
sudo cp -r conf/.password_verification "conf/$INSTANCE_NAME/"

echo "Configuration files copied successfully to conf/$INSTANCE_NAME/"