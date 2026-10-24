import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float } from '@react-three/drei';
import { MathUtils } from 'three';

const GOLD = '#e0aa48';

function Drifters() {
  const group = useRef();
  const items = useMemo(() => Array.from({ length: 11 }, (_, i) => ({
    p: [(Math.random() - 0.5) * 22, (Math.random() - 0.5) * 12, -6 - Math.random() * 8],
    s: 0.35 + Math.random() * 0.7,
    kind: i % 3,
    speed: 0.15 + Math.random() * 0.35,
  })), []);
  useFrame(({ pointer, camera }, dt) => {
    // gentle camera parallax following the cursor
    camera.position.x = MathUtils.damp(camera.position.x, pointer.x * 0.8, 2, dt);
    camera.position.y = MathUtils.damp(camera.position.y, pointer.y * 0.5, 2, dt);
    camera.lookAt(0, 0, 0);
    group.current.rotation.y += dt * 0.012;
  });
  return (
    <group ref={group}>
      {items.map((it, i) => (
        <Float key={i} speed={it.speed * 4} rotationIntensity={1.2} floatIntensity={1.4}>
          <mesh position={it.p} scale={it.s}>
            {it.kind === 0 ? <torusGeometry args={[1, 0.22, 20, 64]} /> : it.kind === 1 ? <octahedronGeometry args={[1, 0]} /> : <icosahedronGeometry args={[0.9, 0]} />}
            <meshStandardMaterial color={it.kind === 1 ? '#8b6cff' : GOLD} metalness={0.7} roughness={0.28} emissive={it.kind === 1 ? '#3a1fd0' : '#6b4308'} emissiveIntensity={0.55} flatShading={it.kind !== 0} transparent opacity={0.55} />
          </mesh>
        </Float>
      ))}
    </group>
  );
}

function Dust({ count = 220 }) {
  const ref = useRef();
  const pos = useMemo(() => Float32Array.from({ length: count * 3 }, (_, i) => (i % 3 === 1 ? (Math.random() - 0.5) * 16 : (Math.random() - 0.5) * 26)), [count]);
  useFrame((_, dt) => { ref.current.rotation.y += dt * 0.02; ref.current.rotation.x += dt * 0.005; });
  return (
    <points ref={ref}>
      <bufferGeometry><bufferAttribute attach="attributes-position" count={count} array={pos} itemSize={3} /></bufferGeometry>
      <pointsMaterial color="#fbe7ae" size={0.04} transparent opacity={0.55} depthWrite={false} sizeAttenuation />
    </points>
  );
}

/** Fixed full-page ambient 3D layer (mounted only on capable, motion-friendly devices). */
export default function Backdrop3D({ paused = false }) {
  return (
    <div aria-hidden="true" style={{ position: 'fixed', inset: 0, zIndex: -1, pointerEvents: 'none', opacity: 0.9 }}>
      <Canvas frameloop={paused ? 'never' : 'always'} camera={{ position: [0, 0, 8], fov: 55 }} dpr={1} gl={{ antialias: false, alpha: true, powerPreference: 'low-power' }}>
        <ambientLight intensity={0.8} />
        <pointLight position={[6, 5, 4]} intensity={90} color="#ffd9a0" />
        <pointLight position={[-7, -3, 2]} intensity={60} color="#7c5cff" />
        <Drifters />
        <Dust />
      </Canvas>
    </div>
  );
}
