import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';

// Rising golden particles.
export default function Sparks({ count = 400 }) {
  const ref = useRef();
  const { positions, speeds } = useMemo(() => {
    const p = new Float32Array(count * 3);
    const s = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      p[i * 3] = (Math.random() - 0.5) * 24;
      p[i * 3 + 1] = Math.random() * 10 - 4;
      p[i * 3 + 2] = (Math.random() - 0.5) * 14;
      s[i] = 0.1 + Math.random() * 0.4;
    }
    return { positions: p, speeds: s };
  }, [count]);

  useFrame((_, dt) => {
    const a = ref.current.geometry.attributes.position;
    for (let i = 0; i < count; i++) {
      let y = a.getY(i) + speeds[i] * dt;
      if (y > 6) y = -4;
      a.setY(i, y);
    }
    a.needsUpdate = true;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={count} array={positions} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial color="#ffd27a" size={0.05} sizeAttenuation transparent opacity={0.8} depthWrite={false} />
    </points>
  );
}
