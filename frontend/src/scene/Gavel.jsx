import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';

// Procedural gavel that strikes its block in a loop.
export default function Gavel(props) {
  const arm = useRef();
  useFrame(({ clock }) => {
    const t = (clock.elapsedTime % 2.4) / 2.4;
    // slow raise, fast strike, short rest
    const angle = t < 0.6 ? (t / 0.6) * 0.9 : t < 0.7 ? 0.9 - ((t - 0.6) / 0.1) * 1.0 : -0.1;
    arm.current.rotation.z = angle;
  });
  const wood = { color: '#8a4b1f', roughness: 0.4, metalness: 0.1 };
  return (
    <group {...props}>
      {/* sound block */}
      <mesh position={[0, -3.7, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[1.1, 1.3, 0.5, 48]} />
        <meshStandardMaterial {...wood} color="#5c2f12" />
      </mesh>
      <group ref={arm} position={[1.3, -3.4, 0]}>
        <group position={[-1.3, 0, 0]}>
          <mesh rotation={[0, 0, Math.PI / 2]} position={[0.9, 1.2, 0]} castShadow>
            <cylinderGeometry args={[0.07, 0.09, 2.6, 20]} />
            <meshStandardMaterial {...wood} />
          </mesh>
          <mesh position={[-0.25, 1.2, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
            <cylinderGeometry args={[0.32, 0.32, 0.9, 32]} />
            <meshStandardMaterial {...wood} color="#a35f2a" />
          </mesh>
          {[-0.6, 0.1].map((x) => (
            <mesh key={x} position={[x, 1.2, 0]} rotation={[0, 0, Math.PI / 2]}>
              <torusGeometry args={[0.32, 0.04, 12, 32]} />
              <meshStandardMaterial color="#ffd27a" metalness={1} roughness={0.2} emissive="#ffb84a" emissiveIntensity={0.4} />
            </mesh>
          ))}
        </group>
      </group>
    </group>
  );
}
