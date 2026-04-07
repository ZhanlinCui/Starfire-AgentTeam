import { ShapeGrid } from "./ShapeGrid";

export function LandingBackground() {
  return (
    <div className="pointer-events-none absolute top-0 left-0 right-0 h-[900px] z-0 overflow-hidden">
      <div className="absolute inset-0 opacity-95">
        <ShapeGrid
          speed={0.15}
          squareSize={40}
          direction="diagonal"
          borderColor="#0056d6"
          hoverFillColor="#66d3ff"
          shape="hexagon"
          hoverTrailAmount={0}
        />
      </div>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_62%_at_50%_8%,rgba(0,86,214,0.34),transparent_62%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(to_bottom,rgba(7,8,12,0.12),rgba(7,8,12,0.78)_65%,rgba(6,9,18,1)_100%)]" />
    </div>
  );
}
