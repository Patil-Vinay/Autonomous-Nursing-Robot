const controlsToggle = document.getElementById('controlsToggle');
const automaticControls = document.querySelector('.automatic-controls');
const automaticToggle = document.getElementById('automaticToggle');
const manualControls = document.querySelector('.manual-controls');
const manualToggle = document.getElementById('manualToggle');


controlsToggle.addEventListener('change', function() {
  if (controlsToggle.checked) {
    automaticControls.style.display = 'none';
    manualControls.style.display = 'flex';
    automaticToggle.classList.remove('toggle-active');
    manualToggle.classList.add('toggle-active');
  } else {
    automaticControls.style.display = 'block';
    manualControls.style.display = 'none';
    automaticToggle.classList.add('toggle-active');
    manualToggle.classList.remove('toggle-active');
  }
});

var canvas = document.getElementById('joystick');
canvas.height = 100;
canvas.width = 100;
var ctx = canvas.getContext('2d');

ctx.beginPath();
ctx.arc(50, 50, 35, 0, 2 * Math.PI);
ctx.fillStyle = '#fff';
ctx.fill();