import { useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Text, RoundedBox } from '@react-three/drei';
import { MathUtils } from 'three';
import Photo from './Photo.jsx';

const STATUS_COLOR = { LIVE: '#37e6a0', SCHEDULED: '#e0aa48', CLOSED: '#ff6b7a', SOLD: '#8b6cff' };

function Card({ auction, angle, radius, active, onClick }) {
  const ref = useRef();
  const gem = useRef();
  const [hover, setHover] = useState(false);
  useFrame((_, dt) => {
    ref.current.scale.setScalar(MathUtils.damp(ref.current.scale.x, active ? 1.22 : hover ? 1.07 : 1, 6, dt));
    if (gem.current) gem.current.rotation.y += dt * 0.8;
  });
  const color = STATUS_COLOR[auction.status] ?? '#a7a2bd';
  const price = auction.current_highest_bid ?? auction.starting_price;
  return (
    <group position={[Math.sin(angle) * radius, 0, Math.cos(angle) * radius]} rotation={[0, angle, 0]}>
      <group
        ref={ref}
        onClick={onClick}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = 'pointer'; }}
        onPointerOut={() => { setHover(false); document.body.style.cursor = 'auto'; }}
      >
        <RoundedBox args={[2.3, 3.1, 0.14]} radius={0.12}>
          <meshPhysicalMaterial color={active ? '#2a2150' : '#17132f'} metalness={0.55} roughness={0.25} clearcoat={1} emissive={active ? '#3a2a80' : '#000000'} emissiveIntensity={0.5} />
        </RoundedBox>
        <Photo
          url={auction.product_images?.[0]}
          size={[1.92, 1.44]}
          position={[0, 0.5, 0.13]}
          fallback={(
            <mesh ref={gem} position={[0, 0.5, 0.35]}>
              <icosahedronGeometry args={[0.5, 0]} />
              <meshStandardMaterial color={`hsl(${(auction.id * 67) % 360},75%,62%)`} metalness={0.9} roughness={0.15} flatShading />
            </mesh>
          )}
        />
        <Text position={[0, -0.55, 0.1]} fontSize={0.17} maxWidth={2} textAlign="center" color="#ffffff" anchorY="middle">{auction.product_name}</Text>
        <Text position={[0, -0.98, 0.1]} fontSize={0.3} color="#fbe7ae">{`₹${Number(price).toLocaleString('en-IN')}`}</Text>
        <Text position={[0, -1.34, 0.1]} fontSize={0.1} color={color} letterSpacing={0.18}>{`${auction.status}  ·  ${auction.bid_count ?? 0} BIDS`}</Text>
      </group>
    </group>
  );
}

export default function Carousel({ auctions, selected, onSelect, onOpen }) {
  const ring = useRef();
  const n = Math.max(auctions.length, 1);
  const step = (Math.PI * 2) / n;
  const radius = Math.max(4.4, n * 0.85);

  useFrame((_, dt) => {
    ring.current.rotation.y = MathUtils.damp(ring.current.rotation.y, -selected * step, 4, dt);
  });

  return (
    <group position={[0, 0.5, -radius + 3]}>
      <group ref={ring}>
        {auctions.map((a, i) => (
          <Card key={a.id} auction={a} angle={i * step} radius={radius} active={i === selected} onClick={() => (i === selected ? onOpen?.(a) : onSelect(i))} />
        ))}
      </group>
    </group>
  );
}
