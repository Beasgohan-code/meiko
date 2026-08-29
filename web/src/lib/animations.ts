import anime from "animejs";

/** Animate a chat bubble entrance (used for both user + assistant messages). */
export function animateMessageIn(el: Element) {
  anime({
    targets: el,
    opacity: [0, 1],
    translateY: [16, 0],
    scale: [0.98, 1],
    easing: "easeOutExpo",
    duration: 520,
  });
}

/** Animate the sidebar / panel slide-in. */
export function animatePanelIn(el: Element, fromX = 24) {
  anime({
    targets: el,
    opacity: [0, 1],
    translateX: [fromX, 0],
    easing: "easeOutQuad",
    duration: 420,
  });
}

/** Staggered entrance for a list of nodes (e.g. suggestion chips, tool badges). */
export function animateStagger(targets: any, delayStep = 60) {
  anime({
    targets,
    opacity: [0, 1],
    translateY: [10, 0],
    delay: anime.stagger(delayStep),
    easing: "easeOutQuad",
    duration: 380,
  });
}

/** Pulse animation for the "send" button on submit. */
export function pulseElement(el: Element) {
  anime({
    targets: el,
    scale: [1, 0.88, 1.05, 1],
    duration: 420,
    easing: "easeInOutQuad",
  });
}

/** Animated gradient-text intro for the hero title. */
export function animateHeroText(el: Element) {
  anime({
    targets: el,
    opacity: [0, 1],
    translateY: [24, 0],
    easing: "easeOutExpo",
    duration: 900,
  });
}

/** Shake animation for error states. */
export function shakeElement(el: Element) {
  anime({
    targets: el,
    translateX: [0, -8, 8, -6, 6, -3, 3, 0],
    duration: 500,
    easing: "easeInOutSine",
  });
}

/** Animated dots for "thinking" indicator. */
export function animateThinkingDots(el: Element) {
  return anime({
    targets: el.querySelectorAll(".dot"),
    translateY: [0, -6, 0],
    delay: anime.stagger(120),
    duration: 700,
    loop: true,
    easing: "easeInOutSine",
  });
}
