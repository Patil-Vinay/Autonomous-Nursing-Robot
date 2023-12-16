// SCOBO tablet page, shows /display/prompt and sends taps on /display/response

const url = 'ws://' + (location.hostname || 'localhost') + ':9090';
const ros = new ROSLIB.Ros({ url: url });

const title = document.getElementById('title');
const text = document.getElementById('text');
const buttons = document.getElementById('buttons');
const status = document.getElementById('status');

ros.on('connection', function () {
  status.textContent = 'Connected to SCOBO';
});

// try again, roslib subscribes the topics again once connected
ros.on('close', function () {
  status.textContent = 'Not connected, retrying';
  setTimeout(function () { ros.connect(url); }, 3000);
});

const prompt = new ROSLIB.Topic({
  ros: ros,
  name: '/display/prompt',
  messageType: 'scobo_interfaces/msg/DisplayPrompt'
});

const response = new ROSLIB.Topic({
  ros: ros,
  name: '/display/response',
  messageType: 'scobo_interfaces/msg/DisplayResponse'
});

function show(msg) {
  buttons.replaceChildren();
  if (!msg.id) {
    title.textContent = 'SCOBO';
    text.textContent = 'Nursing assistant';
    return;
  }
  title.textContent = msg.title;
  text.textContent = msg.text;
  msg.buttons.forEach(function (label) {
    const button = document.createElement('button');
    button.textContent = label;
    button.onclick = function () {
      response.publish({ id: msg.id, button: label });
      buttons.replaceChildren();
      text.textContent = 'Thank you';
    };
    buttons.appendChild(button);
  });
}

prompt.subscribe(show);
