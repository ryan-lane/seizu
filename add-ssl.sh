#!/bin/bash
if [ -f ~/.minica/minica.pem ]
then
  exit
fi

echo "localhost certificate is missing; adding it...";

if ! minica --help &> /dev/null
then
  echo ""
  echo "minica not found. Please install via..."
  echo "  (OSX) brew install minica"
  echo "  (Ubuntu) apt-get install minica"
  echo ""
  echo "We use minica to create a local CA and certificate, for use in the docker-compose containers. This is necessary because websockets on localhost is only allowed over https."
  exit 1
fi

echo ""
echo "Creating a minica CA, and a localhost certificate..."
mkdir -p ~/.minica
pushd ~/.minica > /dev/null
minica -domains localhost -ip-addresses 127.0.0.1
popd > /dev/null

echo ""
echo "Add the minica CA to the system keychain trust..."
echo ""
echo "  (OSX) sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.minica/minica.pem"
echo "  (Ubuntu) sudo cp ~/.minica/minica.pem /usr/local/share/ca-certificates/minica.crt; sudo update-ca-certificates"
echo ""
echo "To remove the CA..."
echo ""
echo "  (OSX) sudo security remove-trusted-cert -d ~/.minica/minica.pem"
echo "  (Ubuntu) sudo rm /usr/local/share/ca-certificates/minica.crt; sudo update-ca-certificates"
