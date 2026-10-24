import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { Float, Stars } from '@react-three/drei';
import { Bloom, EffectComposer, Vignette } from '@react-three/postprocessing';
import Gavel from './Gavel.jsx';
import Sparks from './Sparks.jsx';

/** Art panel on the login / register screens. */
export default function AuthScene() {
  return (
    <Canvas camera={{ position: [0, 0.5, 9], fov: 48 }} dpr={[1, 1.5]} performance={{ min: 0.5 }}>
      <ambientLight intensity={0.6} />
      <spotLight position={[3, 8, 6]} angle={0.5} penumbra={1} intensity={150} color="#ffe2b0" />
      <pointLight position={[-6, 1, 3]} intensity={50} color="#7c5cff" />
      <Suspense fallback={null}>
        <Stars radius={50} depth={30} count={1800} factor={4} fade speed={1} />
        <Float speed={1.4} floatIntensity={0.4} rotationIntensity={0.1}>
          <group position={[-0.4, 3.0, 0]} scale={1.25}><Gavel /></group>
        </Float>
        <Sparks count={260} />
      </Suspense>
      <EffectComposer multisampling={0}>
        <Bloom intensity={0.6} luminanceThreshold={0.6} mipmapBlur />
        <Vignette darkness={0.6} />
      </EffectComposer>
    </Canvas>
  );
}
