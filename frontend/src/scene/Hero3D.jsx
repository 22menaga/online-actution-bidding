import { Suspense } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls, Stars } from '@react-three/drei';
import { Bloom, EffectComposer, Vignette } from '@react-three/postprocessing';
import Carousel from './Carousel.jsx';
import Sparks from './Sparks.jsx';

// Shift the scene right on wide screens so the headline has room on the left.
function Offset({ children }) {
  const { size } = useThree();
  const wide = size.width > 900;
  return <group position={[wide ? 3.2 : 0, wide ? 0 : -0.8, 0]}>{children}</group>;
}

/** 3D landing scene: a ring of live-auction cards. Click the front card to open it. */
export default function Hero3D({ auctions, selected, onSelect, onOpen }) {
  return (
    <Canvas camera={{ position: [0, 1.6, 11], fov: 50 }} dpr={[1, 1.5]} performance={{ min: 0.5 }}>
      <fog attach="fog" args={['#07060c', 14, 34]} />
      <ambientLight intensity={0.55} />
      <spotLight position={[2, 10, 8]} angle={0.55} penumbra={1} intensity={170} color="#ffe2b0" />
      <pointLight position={[-8, 2, 3]} intensity={55} color="#7c5cff" />
      <pointLight position={[9, 1, 3]} intensity={55} color="#ff5c9a" />
      <Suspense fallback={null}>
        <Stars radius={60} depth={40} count={2500} factor={4} fade speed={1} />
        <Offset>
          <Carousel auctions={auctions} selected={selected} onSelect={onSelect} onOpen={onOpen} />
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -2.6, -1]}>
            <circleGeometry args={[9, 64]} />
            <meshStandardMaterial color="#120f22" metalness={0.85} roughness={0.3} transparent opacity={0.85} />
          </mesh>
          <Sparks />
        </Offset>
      </Suspense>
      <OrbitControls enablePan={false} enableZoom={false} minPolarAngle={Math.PI / 2.6} maxPolarAngle={Math.PI / 2.05} />
      <EffectComposer multisampling={0}>
        <Bloom intensity={0.55} luminanceThreshold={0.65} mipmapBlur />
        <Vignette darkness={0.55} />
      </EffectComposer>
    </Canvas>
  );
}
