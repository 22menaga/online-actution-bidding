import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float } from '@react-three/drei';
import { LatheGeometry, Vector2 } from 'three';
import Sparks from './Sparks.jsx';

const GOLD = { color: '#e0aa48', metalness: 0.95, roughness: 0.18, emissive: '#7a4f08', emissiveIntensity: 0.45 };

function Trophy() {
  const ref = useRef();
  const cup = useMemo(() => new LatheGeometry([[0.001, 0], [0.55, 0], [0.7, 0.15], [0.95, 0.9], [1.1, 1.5], [1.0, 1.6], [0.85, 1.4], [0.75, 0.95], [0.4, 0.55], [0.18, 0.35], [0.12, -0.5], [0.5, -0.6], [0.6, -0.75], [0.001, -0.75]].map(([x, y]) => new Vector2(x, y)), 48), []);
  useFrame((_, dt) => { ref.current.rotation.y += dt * 0.8; });
  return (
    <group ref={ref} position={[0, 0.4, 0]}>
      <mesh geometry={cup}><meshStandardMaterial {...GOLD} side={2} /></mesh>
      {[-1, 1].map((s) => (
        <mesh key={s} position={[s * 1.12, 1.05, 0]} rotation={[0, 0, s * 0.2]}>
          <torusGeometry args={[0.38, 0.07, 16, 32, Math.PI * 1.4]} />
          <meshStandardMaterial {...GOLD} />
        </mesh>
      ))}
      <mesh position={[0, -0.95, 0]}><boxGeometry args={[1.5, 0.3, 1.5]} /><meshStandardMaterial color="#17132f" metalness={0.6} roughness={0.3} /></mesh>
    </group>
  );
}

/** Celebratory spinning gold trophy for winners. */
export default function Trophy3D({ height = 220 }) {
  return (
    <div style={{ height, width: '100%' }} aria-hidden="true">
      <Canvas camera={{ position: [0, 1.2, 5.2], fov: 42 }} dpr={[1, 1.75]}>
        <ambientLight intensity={0.7} />
        <spotLight position={[3, 6, 4]} angle={0.5} penumbra={1} intensity={130} color="#ffe2b0" />
        <pointLight position={[-4, 1, 3]} intensity={40} color="#ff5c9a" />
        <Float speed={2} floatIntensity={0.4} rotationIntensity={0.05}><Trophy /></Float>
        <Sparks count={120} />
      </Canvas>
    </div>
  );
}
