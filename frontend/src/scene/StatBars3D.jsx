import { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Html, OrbitControls } from '@react-three/drei';
import { MathUtils } from 'three';

const COLORS = ['#ff5c9a', '#e0aa48', '#8b6cff', '#6ee7d8', '#37e6a0'];

function Bar({ x, value, max, color }) {
  const ref = useRef();
  const h = Math.max(0.08, (value / max) * 2.4);
  useFrame((_, dt) => {
    ref.current.scale.y = MathUtils.damp(ref.current.scale.y, h, 4, dt);
    ref.current.position.y = ref.current.scale.y / 2;
  });
  return (
    <group position={[x, 0, 0]}>
      <mesh ref={ref} scale={[1, 0.01, 1]}>
        <boxGeometry args={[0.8, 1, 0.8]} />
        <meshStandardMaterial color={color} metalness={0.5} roughness={0.3} emissive={color} emissiveIntensity={0.45} />
      </mesh>
      <Html position={[0, h + 0.4, 0]} center distanceFactor={8} style={{ pointerEvents: 'none' }}>
        <div style={{ color: '#fff', font: '700 24px Fraunces,Georgia,serif', lineHeight: 1 }}>{value}</div>
      </Html>
    </group>
  );
}

/** 3D bar chart for the admin control room: items waiting vs live activity (labels in a legend below). */
export default function StatBars3D({ items }) {
  const max = Math.max(...items.map((i) => i.value), 1);
  const gap = 1.5;
  return (
    <div className="card clip">
      <div style={{ height: 230 }}>
        <Canvas camera={{ position: [0, 2.2, 6.6], fov: 42 }} dpr={[1, 1.75]}>
          <ambientLight intensity={0.7} />
          <pointLight position={[4, 6, 4]} intensity={80} color="#ffe2b0" />
          <pointLight position={[-5, 2, 3]} intensity={40} color="#7c5cff" />
          <group position={[0, -1.1, 0]} rotation={[0, -0.2, 0]}>
            <mesh position={[0, -0.06, 0]}><boxGeometry args={[items.length * gap + 0.4, 0.1, 1.5]} /><meshStandardMaterial color="#1d1a3a" metalness={0.7} roughness={0.35} /></mesh>
            {items.map((it, i) => <Bar key={it.label} x={(i - (items.length - 1) / 2) * gap} value={it.value} max={max} color={COLORS[i % COLORS.length]} />)}
          </group>
          <OrbitControls enablePan={false} enableZoom={false} minPolarAngle={Math.PI / 3.2} maxPolarAngle={Math.PI / 2.1} />
        </Canvas>
      </div>
      <div className="row" style={{ justifyContent: 'center', gap: 22, padding: '4px 16px 16px' }}>
        {items.map((it, i) => (
          <span key={it.label} className="small mute" style={{ letterSpacing: '.08em', fontWeight: 600 }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: COLORS[i % COLORS.length], marginRight: 7 }} />{it.label}
          </span>
        ))}
      </div>
    </div>
  );
}
