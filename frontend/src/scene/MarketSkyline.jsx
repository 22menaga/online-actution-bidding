import { useMemo, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Html, OrbitControls } from '@react-three/drei';
import { MathUtils } from 'three';
import { money } from '../ui.jsx';

function Tower({ a, x, z, h, hot, onOpen }) {
  const ref = useRef();
  const [hover, setHover] = useState(false);
  useFrame((_, dt) => {
    // rise into place, then ease toward the hover scale
    const target = hover ? 1.12 : 1;
    ref.current.scale.y = MathUtils.damp(ref.current.scale.y, h * target, 4, dt);
    ref.current.position.y = ref.current.scale.y / 2;
  });
  const color = hot ? '#ff5c9a' : '#e0aa48';
  return (
    <group position={[x, 0, z]}>
      <mesh
        ref={ref}
        scale={[1, 0.01, 1]}
        onClick={(e) => { e.stopPropagation(); onOpen?.(a); }}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = 'pointer'; }}
        onPointerOut={() => { setHover(false); document.body.style.cursor = 'auto'; }}
      >
        <boxGeometry args={[0.8, 1, 0.8]} />
        <meshStandardMaterial color={color} metalness={0.6} roughness={0.28} emissive={color} emissiveIntensity={hover ? 0.9 : hot ? 0.55 : 0.28} />
      </mesh>
      <mesh position={[0, h + 0.18, 0]} scale={hover ? 1.3 : 1}>
        <octahedronGeometry args={[0.16, 0]} />
        <meshStandardMaterial color="#ffffff" emissive={color} emissiveIntensity={1.4} />
      </mesh>
      {hover && (
        <Html position={[0, h + 0.7, 0]} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
          <div style={{ background: 'rgba(14,11,28,.95)', border: '1px solid rgba(224,170,72,.5)', borderRadius: 10, padding: '8px 12px', whiteSpace: 'nowrap', color: '#f4f1ff', font: '600 13px Inter,system-ui,sans-serif' }}>
            {a.product_name}<div style={{ color: '#fbe7ae', fontWeight: 700 }}>{money(a.current_highest_bid ?? a.starting_price, 0)} · {a.bid_count} bids</div>
          </div>
        </Html>
      )}
    </group>
  );
}

/** Interactive 3D "skyline" of live auctions: tower height = current price, pink = ends within the hour. */
export default function MarketSkyline({ auctions, onOpen }) {
  const { towers, cols } = useMemo(() => {
    const prices = auctions.map((a) => Number(a.current_highest_bid ?? a.starting_price));
    const max = Math.max(...prices, 1);
    const cols = Math.ceil(Math.sqrt(auctions.length));
    const towers = auctions.map((a, i) => ({
      a,
      x: (i % cols - (cols - 1) / 2) * 1.5,
      z: (Math.floor(i / cols) - (Math.ceil(auctions.length / cols) - 1) / 2) * 1.5,
      h: 0.5 + 3.4 * (prices[i] / max) ** 0.7,
      hot: a.end_at && new Date(a.end_at) - Date.now() < 3600000,
    }));
    return { towers, cols };
  }, [auctions]);

  return (
    <Canvas camera={{ position: [5.5, 4.6, 7], fov: 45 }} dpr={[1, 1.5]} performance={{ min: 0.5 }}>
      <ambientLight intensity={0.55} />
      <spotLight position={[4, 9, 5]} angle={0.6} penumbra={1} intensity={140} color="#ffe2b0" />
      <pointLight position={[-6, 3, -4]} intensity={50} color="#7c5cff" />
      <fog attach="fog" args={['#07060c', 10, 26]} />
      <gridHelper args={[16, 32, '#3a2f66', '#1d1a3a']} position={[0, 0.001, 0]} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}><circleGeometry args={[8, 64]} /><meshStandardMaterial color="#0d0b18" metalness={0.8} roughness={0.4} /></mesh>
      <group position={[0, 0, 0]}>{towers.map((t) => <Tower key={t.a.id} {...t} onOpen={onOpen} />)}</group>
      <OrbitControls enablePan={false} enableZoom={false} autoRotate autoRotateSpeed={0.7} minPolarAngle={Math.PI / 5} maxPolarAngle={Math.PI / 2.2} target={[0, 1.2, 0]} />
    </Canvas>
  );
}
