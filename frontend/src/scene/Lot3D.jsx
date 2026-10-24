import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, OrbitControls, RoundedBox } from '@react-three/drei';
import Photo from './Photo.jsx';

const DIRS = Array.from({ length: 36 }, () => { const a = Math.random() * Math.PI * 2; const u = 0.4 + Math.random() * 0.9; return [Math.cos(a) * u, 0.6 + Math.random() * 1.4, Math.sin(a) * u]; });

// Gold shockwave ring + spark spray, fired whenever `pulse` changes (i.e. a new bid arrives).
function BidBurst({ pulse }) {
  const t = useRef(-1);
  const first = useRef(true);
  const ring = useRef();
  const pts = useRef();
  const base = useMemo(() => new Float32Array(DIRS.length * 3), []);
  useEffect(() => { if (first.current) { first.current = false; return; } t.current = 0; }, [pulse]);
  useFrame((_, dt) => {
    if (t.current < 0) { ring.current.visible = false; pts.current.visible = false; return; }
    t.current += dt;
    const k = t.current / 1.3;
    if (k >= 1) { t.current = -1; return; }
    ring.current.visible = pts.current.visible = true;
    ring.current.scale.setScalar(1 + k * 5);
    ring.current.material.opacity = (1 - k) * 0.9;
    const a = pts.current.geometry.attributes.position;
    DIRS.forEach((d, i) => a.setXYZ(i, d[0] * k * 2.2, -1.1 + d[1] * k * 2 - k * k * 1.6, d[2] * k * 2.2));
    a.needsUpdate = true;
    pts.current.material.opacity = 1 - k;
  });
  return (
    <group>
      <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.25, 0]} visible={false}>
        <ringGeometry args={[0.9, 1.0, 64]} />
        <meshBasicMaterial color="#fbe7ae" transparent depthWrite={false} />
      </mesh>
      <points ref={pts} visible={false}>
        <bufferGeometry><bufferAttribute attach="attributes-position" count={DIRS.length} array={base} itemSize={3} /></bufferGeometry>
        <pointsMaterial color="#fbe7ae" size={0.09} transparent depthWrite={false} sizeAttenuation />
      </points>
    </group>
  );
}

function Pedestal({ image, hue, pulse }) {
  const gem = useRef();
  useFrame((_, dt) => { if (gem.current) gem.current.rotation.y += dt * 0.6; });
  return (
    <group>
      <mesh position={[0, -1.55, 0]}>
        <cylinderGeometry args={[1.5, 1.8, 0.5, 64]} />
        <meshStandardMaterial color="#e0aa48" metalness={0.9} roughness={0.22} emissive="#6b4308" emissiveIntensity={0.35} />
      </mesh>
      <mesh position={[0, -1.25, 0]}>
        <cylinderGeometry args={[1.3, 1.3, 0.1, 64]} />
        <meshStandardMaterial color="#17132f" metalness={0.6} roughness={0.3} />
      </mesh>
      <BidBurst pulse={pulse} />
      <Float speed={2} floatIntensity={0.5} rotationIntensity={0.15}>
        {image ? (
          <group position={[0, 0.1, 0]}>
            <RoundedBox args={[2.5, 1.95, 0.12]} radius={0.08}>
              <meshStandardMaterial color="#e0aa48" metalness={0.95} roughness={0.2} />
            </RoundedBox>
            <Photo url={image} size={[2.3, 1.75]} position={[0, 0, 0.1]} />
            <group rotation={[0, Math.PI, 0]}><Photo url={image} size={[2.3, 1.75]} position={[0, 0, 0.1]} /></group>
          </group>
        ) : (
          <mesh ref={gem} position={[0, 0.1, 0]}>
            <icosahedronGeometry args={[1, 0]} />
            <meshStandardMaterial color={`hsl(${hue},75%,62%)`} metalness={0.9} roughness={0.15} flatShading />
          </mesh>
        )}
      </Float>
    </group>
  );
}

/** Orbitable showcase of the lot: drag to rotate. */
export default function Lot3D({ image, id, pulse = 0 }) {
  return (
    <Canvas camera={{ position: [0, 0.6, 5.4], fov: 45 }} dpr={[1, 1.5]} performance={{ min: 0.5 }}>
      <ambientLight intensity={0.7} />
      <spotLight position={[3, 6, 5]} angle={0.5} penumbra={1} intensity={110} color="#ffe2b0" />
      <pointLight position={[-4, 1, 3]} intensity={30} color="#7c5cff" />
      <Suspense fallback={null}><Pedestal image={image} hue={(id * 67) % 360} pulse={pulse} /></Suspense>
      <OrbitControls enablePan={false} enableZoom={false} autoRotate autoRotateSpeed={1.2} minPolarAngle={Math.PI / 3} maxPolarAngle={Math.PI / 1.9} />
    </Canvas>
  );
}
