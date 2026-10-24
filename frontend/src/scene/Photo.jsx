import { Component, Suspense } from 'react';
import { useLoader } from '@react-three/fiber';
import { DoubleSide, FrontSide, TextureLoader } from 'three';

// A missing/broken image must never take the whole 3D scene down: fall back instead.
class Boundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

function Loaded({ url, size, position, double }) {
  const map = useLoader(TextureLoader, url);
  return (
    <mesh position={position}>
      <planeGeometry args={size} />
      <meshBasicMaterial map={map} toneMapped={false} side={double ? DoubleSide : FrontSide} />
    </mesh>
  );
}

/** Image plane for 3D scenes. Shows `fallback` while loading, when there is no url, or if loading fails. */
export default function Photo({ url, size = [1.9, 1.43], position = [0, 0, 0], fallback = null, double = false }) {
  if (!url) return fallback;
  return (
    <Boundary key={url} fallback={fallback}>
      <Suspense fallback={fallback}>
        <Loaded url={url} size={size} position={position} double={double} />
      </Suspense>
    </Boundary>
  );
}
