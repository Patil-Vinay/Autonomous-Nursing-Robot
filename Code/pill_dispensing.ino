//Reference https://randomnerdtutorials.com/esp8266-nodemcu-http-get-post-arduino/#http-get-2
//https://github.com/esp8266/Arduino/blob/master/libraries/DNSServer/examples/CaptivePortal/CaptivePortal.ino

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <Arduino_JSON.h>
#include <Servo.h>
#include <ESP8266WebServer.h>
#include <EEPROM.h>
#include <DNSServer.h>
#include <ESP8266mDNS.h>

const char* serverName = "https://scobobot.pythonanywhere.com/get-medicine/";

const byte DNS_PORT = 53;
IPAddress apIP(172, 217, 28, 1);
DNSServer dnsServer;
ESP8266WebServer server(80);

const int buttonPin = 3; // Button pin to change to configuration mode

unsigned long lastTime = 0;
unsigned long timerDelay = 500;

Servo servo1,servo2,servo3;
int servoPin1 = 5,servoPin2 = 4,servoPin3= 0;
int servoAngle = 180;

 String handleConfig = ""
"<html><head><title>ScoboBot WiFi Configuration</title></head><body>"
"<div style='display: flex; justify-content: center; align-items: center; height: 100vh;'>"
"<div style='background-color: #f2f2f2; padding: 20px; border-radius: 5px;'>"
"<h1>WiFi Configuration</h1>"
"<form method='POST' action='/saveconfig'>"
"<label for='ssid'>SSID:</label><br>"
"<input type='text' id='ssid' name='ssid' style='width: 250px; padding: 10px;'><br><br>"
"<label for='password'>Password:</label><br>"
"<input type='password' id='password' name='password' style='width: 250px; padding: 10px;'><br><br>"
"<input type='submit' value='Save' style='padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;'>"
"</form>"
"</div>"
"</div>"
"<style>body { font-family: Arial, sans-serif; }</style></body></html>"; // Add a basic font-family style

void handleSaveConfig() {
  String ssid = server.arg("ssid");
  String password = server.arg("password");

  // Save the new WiFi credentials
  saveWiFiCredentials(ssid, password);
    Serial.println("Credentials Saved!");
String html = "<html><head><title>ScoboBot WiFi Configuration</title></head><body>";
  html += "<div style='display: flex; justify-content: center; align-items: center; height: 100vh;'>";
  html += "<div style='background-color: #f2f2f2; padding: 20px; border-radius: 5px;'>";
  html += "<h1 style='color: #4CAF50;'>Configuration Saved!</h1>";
  html += "<p>Your WiFi configuration has been saved successfully.</p>";
  html += "<p>Please restart the device to apply the new settings.</p>";
  html += "<p>Also press config switch to turn off config mode!</p>";
  html += "</div>";
  html += "</div>";
  html += "<style>body { font-family: Arial, sans-serif; }</style></body></html>"; // Add a basic font-family style
  server.send(200, "text/html", html);
}

void saveWiFiCredentials(const String& ssid, const String& password) {
  // Save the WiFi credentials to EEPROM
  int ssidLength = ssid.length() + 1;
  int passwordLength = password.length() + 1;

  EEPROM.begin(512);
  EEPROM.write(0, ssidLength);
  for (int i = 0; i < ssidLength; ++i) {
    EEPROM.write(i + 1, ssid[i]);
  }
  EEPROM.write(ssidLength + 1, passwordLength);
  for (int i = 0; i < passwordLength; ++i) {
    EEPROM.write(ssidLength + 2 + i, password[i]);
  }
  EEPROM.commit();
  EEPROM.end();
}

void loadWiFiCredentials(String& ssid, String& password) {
  // Load the WiFi credentials from EEPROM
  EEPROM.begin(512);
  int ssidLength = EEPROM.read(0);
  for (int i = 0; i < ssidLength; ++i) {
    ssid += char(EEPROM.read(i + 1));
  }
  int passwordLength = EEPROM.read(ssidLength + 1);
  for (int i = 0; i < passwordLength; ++i) {
    password += char(EEPROM.read(ssidLength + 2 + i));
  }
  EEPROM.end();
}

void setup() {
  Serial.begin(115200);

  pinMode(buttonPin, INPUT_PULLUP); //configuration mode pin

  servo1.attach(servoPin1,500,2400);
  servo1.write(0);
  servo2.attach(servoPin2,500,2400);
  servo2.write(0);
  servo3.attach(servoPin3,500,2400);
  servo3.write(0);

pinMode(14, INPUT_PULLUP);
pinMode(12, INPUT_PULLUP);
pinMode(13, INPUT_PULLUP);

// Check if the button is pressed during startup
  if (digitalRead(buttonPin) == LOW) {
    delay(1000);
    // If the button is pressed, enter WiFi configuration mode
    Serial.println("\nEntering WiFi configuration mode!");
    WiFi.mode(WIFI_AP);
    WiFi.softAPConfig(apIP, apIP, IPAddress(255, 255, 255, 0));
    WiFi.softAP("ScoboBot_WifiConnect"); // Create an access point
    IPAddress apIP = WiFi.softAPIP();
    Serial.print("AP IP address: ");
    Serial.println(apIP);
    dnsServer.start(DNS_PORT, "*", apIP);
    if (MDNS.begin("scobobot")) {
    Serial.println("MDNS responder started");
  }
    server.onNotFound([]() {
    server.send(200, "text/html", handleConfig);
  });
    server.on("/saveconfig", handleSaveConfig);
    server.begin();
  Serial.println("Web server started\n");
  }else {
    // If the button is not pressed, load WiFi credentials and connect to WiFi
    String ssid, password;
    loadWiFiCredentials(ssid, password);
    Serial.println("Connecting to WiFi...");
    WiFi.begin(ssid.c_str(), password.c_str());
    while (WiFi.status() != WL_CONNECTED) {
      delay(1000);
      Serial.print(".");
    }
    Serial.println("");
    Serial.println("Connected to WiFi");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.println("\nConnected to https://scobobot.pythonanywhere.com !\n");
    Serial.println("Timer set to 500 mseconds (timerDelay variable), it will take 500 mseconds before publishing the first reading.\n");
  }

}

void loop() {

    if(digitalRead(buttonPin) == LOW){ //for configuration mode
    dnsServer.processNextRequest();
    MDNS.update();
    server.handleClient();
  }
  
  else{ //when not in config mode i.e normal mode
  // Check the status of the switches
   int switch1State = digitalRead(14);
   int switch2State = digitalRead(12);
   int switch3State = digitalRead(13);

  // Control the servos based on the switch states
  if (switch1State == 0) {
    servo1.write(servoAngle);
    delay(2000);
    servo1.write(0);
    Serial.println("\nSwitch 1: Medicine1 Dispensed!");
  }

  if (switch2State == 0) {
    servo2.write(servoAngle);
    delay(2000);
    servo2.write(0);
    Serial.println("\nSwitch 2: Medicine2 Dispensed!");
  }

  if (switch3State == 0) {
    servo3.write(servoAngle);
    delay(2000);
    servo3.write(0);
    Serial.println("\nSwitch 3: Medicine3 Dispensed!");
  }
else{
  servo1.write(0);
   servo2.write(0);
    servo3.write(0);
}
  
  if ((millis() - lastTime) > timerDelay) {
    if (WiFi.status() == WL_CONNECTED) {
      String response = httpGETRequest(serverName);
      Serial.println(response);

      JSONVar json = JSON.parse(response);
      if (JSON.typeof(json) == "undefined") {
        Serial.println("Parsing input failed!\n");
        return;
      }

      JSONVar medicineValue = json["medicine"];
      if (JSON.typeof(medicineValue) == "number") {
        int intValue = int(medicineValue);
        Serial.print("Medicine value (int): ");
        Serial.println(intValue);


      } else if (JSON.typeof(medicineValue) == "string") {
        String strValue = String(medicineValue);
        Serial.print("Medicine value (string): ");
        Serial.println(strValue);
          if (strValue == "1") {
          servo1.write(servoAngle);
          delay(2000);
          servo1.write(0);
          Serial.println("\nMedicine 1 Dispensed!");
        }
                  if (strValue == "2") {
          servo2.write(servoAngle);
          delay(2000);
          servo2.write(0);
          Serial.println("\nMedicine 2 Dispensed!");
        }
                  if (strValue == "3") {
          servo3.write(servoAngle);
          delay(2000);
          servo3.write(0);
          Serial.println("\nMedicine 3 Dispensed!");
        }
      } else {
        Serial.println("Invalid medicine value!\n");
      }
    } else {
      Serial.println("WiFi Disconnected\nRestart Device!\n");
    }
    lastTime = millis();
  }
  } //when not in config mode
}


String httpGETRequest(const char* serverName) {
  WiFiClientSecure client;
  HTTPClient http;

  // Disable certificate verification (only for testing, not recommended for production)
  client.setInsecure();

  http.begin(client, serverName);

  int httpResponseCode = http.GET();

  String payload = "{}";

  if (httpResponseCode > 0) {
    Serial.print("\nHTTP Response code: ");
    Serial.println(httpResponseCode);
    payload = http.getString();
  } else {
    Serial.print("Error code: ");
    Serial.println(httpResponseCode);
  }

  http.end();
  return payload;
}
