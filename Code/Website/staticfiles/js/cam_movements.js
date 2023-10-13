const rotateLeftBtn = document.getElementById('rotateLeftBtn');
const rotateRightBtn = document.getElementById('rotateRightBtn');
const tiltUpBtn = document.getElementById('tiltUpBtn');
const tiltDownBtn = document.getElementById('tiltDownBtn');
const resetBtn = document.getElementById('resetBtn');
const movementMessage = document.getElementById('movementMsg');

let rotationAngle = 0;
let tiltAngle = 0;
let toReset = 0;

let rotateInterval;
let tiltInterval;
const controlsURL = "https://scobobot.pythonanywhere.com/send-movements/";

rotateLeftBtn.addEventListener('mousedown', rotateLeft);
rotateLeftBtn.addEventListener('touchstart', rotateLeft);

rotateRightBtn.addEventListener('mousedown', rotateRight);
rotateRightBtn.addEventListener('touchstart', rotateRight);

rotateLeftBtn.addEventListener('mouseup', function() {
    sendMovements(1)
});
rotateLeftBtn.addEventListener('touchend', function() {
    sendMovements(1)
});

rotateRightBtn.addEventListener('mouseup', function() {
    sendMovements(1)
});
rotateRightBtn.addEventListener('touchend', function() {
    sendMovements(1)
});

tiltUpBtn.addEventListener('mousedown', tiltUp);
tiltUpBtn.addEventListener('touchstart', tiltUp);

tiltDownBtn.addEventListener('mousedown', tiltDown);
tiltDownBtn.addEventListener('touchstart', tiltDown);

tiltUpBtn.addEventListener('mouseup', function() {
    sendMovements(2)
});
tiltUpBtn.addEventListener('touchend', function() {
    sendMovements(2)
});

tiltDownBtn.addEventListener('mouseup', function() {
    sendMovements(2)
})
tiltDownBtn.addEventListener('touchend', function() {
    sendMovements(2)
})


function rotateLeft() {
    rotationAngle -= 5;
    rotateInterval = setInterval(function() {
        rotationAngle -= 5;
        movementMessage.innerHTML = 'Rotate: ' + rotationAngle;
    }, 200);
}

function rotateRight() {
    rotationAngle += 5;
    rotateInterval = setInterval(function() {
        rotationAngle += 5;
        movementMessage.innerHTML = 'Rotate: ' + rotationAngle;
    }, 200);
}

function tiltUp() {
    tiltAngle -= 5;
    tiltInterval = setInterval(function() {
        tiltAngle -= 5;
        movementMessage.innerHTML = 'Tilt: ' + tiltAngle;
    }, 200);
}

function tiltDown() {
    tiltAngle += 5;
    tiltInterval = setInterval(function() {
        tiltAngle += 5;
        movementMessage.innerHTML = 'Tilt: ' + tiltAngle;
    }, 200);
}

resetBtn.addEventListener('click', function() {
    toReset = 1;
    sendMovements(3);
})


function sendMovements(movementCategory) {
    clearInterval(rotateInterval);
    clearInterval(tiltInterval);
    movementData = {'rotate': rotationAngle, 'tilt': tiltAngle, 'reset': toReset};

    fetch(controlsURL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify(movementData)
    })
    .then(response => response.json())
    .then(result => console.log(result))
    .catch(error => console.log(error));

    if (movementCategory === 1) {
        movementMessage.innerHTML = 'Rotated by ' + rotationAngle;
    } else if (movementCategory === 2) {
        movementMessage.innerHTML = 'Tilted by ' + tiltAngle;
    } else if (movementCategory === 3) {
        movementMessage.innerHTML = 'Reset to default position';
    }

    rotationAngle = 0;
    tiltAngle = 0;
    toReset = 0;
}
