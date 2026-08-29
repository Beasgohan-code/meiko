import { useEffect, useRef } from "react";
import * as THREE from "three";

interface MeikoOrbProps {
  state: "idle" | "thinking" | "speaking" | "tool";
  size?: number;
}

/**
 * Meiko's animated 3D avatar — a living, glowing orb built with Three.js.
 * Reacts to agent state:
 *   idle     -> slow gentle breathing pulse
 *   thinking -> faster swirling distortion + color shift (violet -> cyan)
 *   tool     -> sharp flicker / spark particles (using a tool)
 *   speaking -> rhythmic pulse synced loosely to output
 */
export default function MeikoOrb({ state, size = 320 }: MeikoOrbProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const width = size;
    const height = size;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 0, 5.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    // --- Core orb (icosahedron with custom shader-like distortion via vertex displacement) ---
    const geometry = new THREE.IcosahedronGeometry(1.4, 12);
    const baseColorA = new THREE.Color("#7c5cff"); // violet
    const baseColorB = new THREE.Color("#22d3ee"); // cyan
    const material = new THREE.MeshPhysicalMaterial({
      color: baseColorA,
      metalness: 0.3,
      roughness: 0.15,
      transmission: 0.55,
      thickness: 1.2,
      emissive: new THREE.Color("#3a1f9e"),
      emissiveIntensity: 0.6,
      clearcoat: 1,
      clearcoatRoughness: 0.2,
    });
    const orb = new THREE.Mesh(geometry, material);
    scene.add(orb);

    const originalPositions = geometry.attributes.position.array.slice();

    // --- Wireframe shell for a "digital / agentic" feel ---
    const wireGeo = new THREE.IcosahedronGeometry(1.75, 2);
    const wireMat = new THREE.MeshBasicMaterial({ color: "#8b7bff", wireframe: true, transparent: true, opacity: 0.18 });
    const wireMesh = new THREE.Mesh(wireGeo, wireMat);
    scene.add(wireMesh);

    // --- Floating particle field ---
    const particleCount = 140;
    const particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i++) {
      const r = 2.4 + Math.random() * 1.6;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }
    particleGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const particleMat = new THREE.PointsMaterial({ color: "#a5b4fc", size: 0.02, transparent: true, opacity: 0.6 });
    const particles = new THREE.Points(particleGeo, particleMat);
    scene.add(particles);

    // --- Lighting ---
    const keyLight = new THREE.PointLight("#c4b5fd", 3.5, 20);
    keyLight.position.set(3, 3, 3);
    scene.add(keyLight);
    const rimLight = new THREE.PointLight("#22d3ee", 2, 20);
    rimLight.position.set(-3, -2, -2);
    scene.add(rimLight);
    scene.add(new THREE.AmbientLight("#1a1030", 1.2));

    let frameId: number;
    let t = 0;
    const noise = (x: number, y: number, z: number, freq: number, time: number) =>
      Math.sin(x * freq + time) * Math.cos(y * freq - time * 0.8) * Math.sin(z * freq + time * 1.2);

    const animate = () => {
      frameId = requestAnimationFrame(animate);
      t += 0.016;

      const st = stateRef.current;
      const speed = st === "thinking" ? 2.2 : st === "tool" ? 3.2 : st === "speaking" ? 1.6 : 0.6;
      const amp = st === "thinking" ? 0.14 : st === "tool" ? 0.22 : st === "speaking" ? 0.1 : 0.045;
      const targetColor = st === "thinking" || st === "tool" ? baseColorB : baseColorA;

      // vertex displacement for organic "alive" surface
      const posAttr = geometry.attributes.position;
      for (let i = 0; i < posAttr.count; i++) {
        const ox = originalPositions[i * 3];
        const oy = originalPositions[i * 3 + 1];
        const oz = originalPositions[i * 3 + 2];
        const n = noise(ox, oy, oz, 2.2, t * speed);
        const scale = 1 + n * amp;
        posAttr.setXYZ(i, ox * scale, oy * scale, oz * scale);
      }
      posAttr.needsUpdate = true;
      geometry.computeVertexNormals();

      orb.rotation.y += 0.0025 * speed;
      orb.rotation.x = Math.sin(t * 0.3) * 0.15;
      wireMesh.rotation.y -= 0.0018 * speed;
      wireMesh.rotation.x += 0.0012 * speed;
      particles.rotation.y += 0.0006 * speed;

      material.color.lerp(targetColor, 0.02);
      material.emissiveIntensity = 0.5 + Math.sin(t * speed) * 0.25 * (st === "idle" ? 0.5 : 1);

      const pulse = 1 + Math.sin(t * speed * 1.4) * (st === "idle" ? 0.015 : 0.04);
      orb.scale.setScalar(pulse);

      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      // fixed size widget; no-op unless container resizes responsively
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", handleResize);
      mount.removeChild(renderer.domElement);
      geometry.dispose();
      wireGeo.dispose();
      particleGeo.dispose();
      material.dispose();
      wireMat.dispose();
      particleMat.dispose();
      renderer.dispose();
    };
  }, [size]);

  return <div ref={mountRef} className="meiko-orb" style={{ width: size, height: size }} />;
}
