"use strict";

const canvas = document.getElementById("gameCanvas");
const context = canvas.getContext("2d");
const gameScreen = document.getElementById("gameScreen");
const overlay = document.getElementById("gameOverlay");
const overlayKicker = document.getElementById("overlayKicker");
const overlayTitle = document.getElementById("overlayTitle");
const overlayDescription = document.getElementById("overlayDescription");
const launchButton = document.getElementById("launchButton");
const gameStatus = document.getElementById("gameStatus");
const scoreValue = document.getElementById("scoreValue");
const shieldValue = document.getElementById("shieldValue");
const worldValue = document.getElementById("worldValue");
const worldButtons = {
    moon: document.getElementById("moonWorld"),
    mars: document.getElementById("marsWorld")
};

const keys = new Set();
const touchInput = { left: false, right: false, fire: false };
const rocks = [];
const shots = [];
const particles = [];
const stars = [];
const worldPalette = {
    moon: {
        rocks: ["#929aa5", "#b3bac2", "#747e8a", "#d0d4d8"],
        detail: "#535e6c",
        shot: "#b9e8ff",
        glow: "rgba(151, 204, 235, 0.12)"
    },
    mars: {
        rocks: ["#a9583e", "#c77950", "#814332", "#d28b5b"],
        detail: "#593126",
        shot: "#ffd1a3",
        glow: "rgba(205, 112, 67, 0.15)"
    }
};

let width = 0;
let height = 0;
let pixelRatio = 1;
let world = "moon";
let running = false;
let score = 0;
let shields = 3;
let shipX = 0;
let spawnTimer = 0;
let shotTimer = 0;
let previousFrame = 0;
let animationFrame = 0;

function resizeCanvas() {
    const bounds = canvas.getBoundingClientRect();
    width = Math.max(1, bounds.width);
    height = Math.max(1, bounds.height);
    pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    shipX = Math.min(Math.max(shipX || width / 2, 22), width - 22);

    stars.length = 0;
    const starCount = Math.max(35, Math.round((width * height) / 6500));
    for (let index = 0; index < starCount; index += 1) {
        stars.push({
            x: Math.random() * width,
            y: Math.random() * height,
            size: Math.random() * 1.4 + 0.35,
            phase: Math.random() * Math.PI * 2
        });
    }
    drawScene(performance.now());
}

function setWorld(nextWorld) {
    if (running || !worldPalette[nextWorld]) return;
    world = nextWorld;
    gameScreen.dataset.world = world;
    worldValue.textContent = world.toUpperCase();
    for (const [name, button] of Object.entries(worldButtons)) {
        button.setAttribute("aria-pressed", String(name === world));
    }
    gameStatus.textContent = `${world.toUpperCase()} MISSION READY`;
    drawScene(performance.now());
}

function updateStats() {
    scoreValue.textContent = String(score).padStart(4, "0");
    shieldValue.textContent = String(shields).padStart(2, "0");
}

function startMission() {
    score = 0;
    shields = 3;
    rocks.length = 0;
    shots.length = 0;
    particles.length = 0;
    spawnTimer = 0.45;
    shotTimer = 0;
    previousFrame = 0;
    running = true;
    overlay.hidden = true;
    launchButton.textContent = "Restart mission";
    for (const button of Object.values(worldButtons)) button.disabled = true;
    updateStats();
    gameStatus.textContent = `${world.toUpperCase()} MISSION IN PROGRESS`;
    cancelAnimationFrame(animationFrame);
    animationFrame = requestAnimationFrame(frame);
}

function endMission() {
    running = false;
    overlayKicker.textContent = "MISSION COMPLETE";
    overlayTitle.textContent = "Lander offline";
    overlayDescription.textContent = `The rocks won this round. You cleared ${score} points from the ${world} field.`;
    launchButton.textContent = "Try again";
    overlay.hidden = false;
    gameStatus.textContent = "MISSION ENDED";
    for (const button of Object.values(worldButtons)) button.disabled = false;
    drawScene(performance.now());
}

function addRock() {
    const radius = 13 + Math.random() * 14;
    const palette = worldPalette[world];
    const points = [];
    const pointCount = 9;
    for (let index = 0; index < pointCount; index += 1) {
        points.push(0.76 + Math.random() * 0.32);
    }
    rocks.push({
        x: radius + Math.random() * Math.max(1, width - radius * 2),
        y: -radius,
        radius,
        speed: 75 + Math.random() * 50 + Math.min(score, 500) * 0.08,
        rotation: Math.random() * Math.PI * 2,
        spin: (Math.random() - 0.5) * 1.2,
        color: palette.rocks[Math.floor(Math.random() * palette.rocks.length)],
        detail: palette.detail,
        points
    });
}

function fireShot() {
    shots.push({
        x: shipX,
        y: height - 48,
        speed: 490
    });
    shotTimer = 0.24;
}

function createBurst(x, y, color, count = 10) {
    for (let index = 0; index < count; index += 1) {
        const angle = Math.random() * Math.PI * 2;
        const speed = 35 + Math.random() * 125;
        particles.push({
            x,
            y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            life: 0.25 + Math.random() * 0.4,
            maxLife: 0.65,
            size: 1 + Math.random() * 2.2,
            color
        });
    }
}

function update(delta) {
    const movingLeft = keys.has("ArrowLeft") || keys.has("KeyA") || touchInput.left;
    const movingRight = keys.has("ArrowRight") || keys.has("KeyD") || touchInput.right;
    if (movingLeft !== movingRight) {
        shipX += (movingRight ? 1 : -1) * 310 * delta;
        shipX = Math.max(20, Math.min(width - 20, shipX));
    }

    shotTimer -= delta;
    if ((keys.has("Space") || touchInput.fire) && shotTimer <= 0) fireShot();

    spawnTimer -= delta;
    if (spawnTimer <= 0) {
        addRock();
        spawnTimer = Math.max(0.38, 0.92 - score / 900) + Math.random() * 0.28;
    }

    for (const shot of shots) shot.y -= shot.speed * delta;
    for (const rock of rocks) {
        rock.y += rock.speed * delta;
        rock.rotation += rock.spin * delta;
    }
    for (const particle of particles) {
        particle.x += particle.vx * delta;
        particle.y += particle.vy * delta;
        particle.vx *= 0.985;
        particle.vy *= 0.985;
        particle.life -= delta;
    }

    for (let rockIndex = rocks.length - 1; rockIndex >= 0; rockIndex -= 1) {
        const rock = rocks[rockIndex];
        const hitIndex = shots.findIndex((shot) =>
            Math.hypot(shot.x - rock.x, shot.y - rock.y) < rock.radius
        );
        if (hitIndex !== -1) {
            shots.splice(hitIndex, 1);
            rocks.splice(rockIndex, 1);
            score += 10;
            createBurst(rock.x, rock.y, rock.color);
            updateStats();
            continue;
        }

        if (rock.y + rock.radius >= height - 43) {
            rocks.splice(rockIndex, 1);
            shields -= 1;
            createBurst(rock.x, height - 40, worldPalette[world].shot, 7);
            updateStats();
            if (shields <= 0) {
                endMission();
                return;
            }
        }
    }

    for (let index = shots.length - 1; index >= 0; index -= 1) {
        if (shots[index].y < -8) shots.splice(index, 1);
    }
    for (let index = particles.length - 1; index >= 0; index -= 1) {
        if (particles[index].life <= 0) particles.splice(index, 1);
    }
}

function drawShip(time) {
    const shipY = height - 29;
    context.save();
    context.translate(shipX, shipY);

    if (running) {
        const flicker = 7 + Math.sin(time / 55) * 2;
        context.beginPath();
        context.moveTo(-6, 9);
        context.lineTo(0, 13 + flicker);
        context.lineTo(6, 9);
        context.closePath();
        context.fillStyle = world === "mars" ? "rgba(255, 158, 93, 0.82)" : "rgba(141, 215, 255, 0.82)";
        context.fill();
    }

    context.beginPath();
    context.moveTo(0, -15);
    context.lineTo(11, 6);
    context.lineTo(7, 10);
    context.lineTo(-7, 10);
    context.lineTo(-11, 6);
    context.closePath();
    context.fillStyle = "#d9e2ea";
    context.strokeStyle = worldPalette[world].shot;
    context.lineWidth = 1.5;
    context.fill();
    context.stroke();

    context.beginPath();
    context.arc(0, 0, 4, Math.PI, 0);
    context.fillStyle = worldPalette[world].shot;
    context.fill();

    context.beginPath();
    context.moveTo(-8, 7);
    context.lineTo(-13, 13);
    context.moveTo(8, 7);
    context.lineTo(13, 13);
    context.strokeStyle = "#9caaba";
    context.lineWidth = 2;
    context.stroke();
    context.restore();
}

function drawRock(rock) {
    context.save();
    context.translate(rock.x, rock.y);
    context.rotate(rock.rotation);
    context.beginPath();
    for (let index = 0; index < rock.points.length; index += 1) {
        const angle = (index / rock.points.length) * Math.PI * 2;
        const radius = rock.radius * rock.points[index];
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;
        if (index === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
    }
    context.closePath();
    context.fillStyle = rock.color;
    context.strokeStyle = "rgba(240, 244, 248, 0.36)";
    context.lineWidth = 1.2;
    context.fill();
    context.stroke();
    context.beginPath();
    context.arc(-rock.radius * 0.2, -rock.radius * 0.12, rock.radius * 0.19, 0, Math.PI * 2);
    context.arc(rock.radius * 0.28, rock.radius * 0.22, rock.radius * 0.12, 0, Math.PI * 2);
    context.fillStyle = rock.detail;
    context.globalAlpha = 0.65;
    context.fill();
    context.restore();
}

function drawScene(time) {
    context.clearRect(0, 0, width, height);
    const palette = worldPalette[world];
    const glow = context.createRadialGradient(width / 2, height, 0, width / 2, height, height * 0.75);
    glow.addColorStop(0, palette.glow);
    glow.addColorStop(1, "rgba(0, 0, 0, 0)");
    context.fillStyle = glow;
    context.fillRect(0, 0, width, height);

    for (const star of stars) {
        const alpha = 0.35 + (Math.sin(time / 800 + star.phase) + 1) * 0.25;
        context.globalAlpha = alpha;
        context.fillStyle = "#e9f2fb";
        context.fillRect(star.x, star.y, star.size, star.size);
    }
    context.globalAlpha = 1;

    context.strokeStyle = world === "mars" ? "rgba(205, 126, 87, 0.18)" : "rgba(161, 197, 219, 0.16)";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(0, height - 43);
    context.lineTo(width, height - 43);
    context.stroke();

    for (const shot of shots) {
        context.beginPath();
        context.moveTo(shot.x, shot.y + 7);
        context.lineTo(shot.x, shot.y - 7);
        context.strokeStyle = palette.shot;
        context.lineWidth = 3;
        context.shadowBlur = 12;
        context.shadowColor = palette.shot;
        context.stroke();
        context.shadowBlur = 0;
    }
    for (const rock of rocks) drawRock(rock);
    for (const particle of particles) {
        context.globalAlpha = Math.max(0, particle.life / particle.maxLife);
        context.fillStyle = particle.color;
        context.fillRect(particle.x, particle.y, particle.size, particle.size);
    }
    context.globalAlpha = 1;
    drawShip(time);
}

function frame(time) {
    if (!running) return;
    const delta = previousFrame === 0 ? 0 : Math.min((time - previousFrame) / 1000, 0.035);
    previousFrame = time;
    update(delta);
    drawScene(time);
    if (running) animationFrame = requestAnimationFrame(frame);
}

function isTyping(target) {
    return target instanceof HTMLElement
        && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
}

launchButton.addEventListener("click", startMission);
worldButtons.moon.addEventListener("click", () => setWorld("moon"));
worldButtons.mars.addEventListener("click", () => setWorld("mars"));

window.addEventListener("keydown", (event) => {
    if (isTyping(event.target)) return;
    const gameKey = ["ArrowLeft", "ArrowRight", "KeyA", "KeyD", "Space"].includes(event.code);
    if (!gameKey || !running) return;
    if (event.code === "Space" || event.code.startsWith("Arrow")) event.preventDefault();
    keys.add(event.code);
});

window.addEventListener("keyup", (event) => {
    keys.delete(event.code);
});
window.addEventListener("blur", () => keys.clear());

for (const button of document.querySelectorAll(".touch-button")) {
    const control = button.dataset.control;
    const release = () => {
        touchInput[control] = false;
        button.classList.remove("is-active");
    };
    button.addEventListener("pointerdown", (event) => {
        if (!running) return;
        event.preventDefault();
        button.setPointerCapture(event.pointerId);
        touchInput[control] = true;
        button.classList.add("is-active");
    });
    button.addEventListener("pointerup", release);
    button.addEventListener("pointercancel", release);
    button.addEventListener("lostpointercapture", release);
}

if ("ResizeObserver" in window) {
    new ResizeObserver(resizeCanvas).observe(canvas);
} else {
    window.addEventListener("resize", resizeCanvas);
}
resizeCanvas();
