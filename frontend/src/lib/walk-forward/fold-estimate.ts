export type WalkForwardWindowValues = {
  trainCandles: number;
  testCandles: number;
  stepCandles: number;
  gapCandles: number;
};

export function estimateWalkForwardFoldCount(
  candleCount: number,
  windows: WalkForwardWindowValues,
): number | null {
  const { trainCandles, testCandles, stepCandles, gapCandles } = windows;

  if (
    !Number.isInteger(candleCount) ||
    !Number.isInteger(trainCandles) ||
    !Number.isInteger(testCandles) ||
    !Number.isInteger(stepCandles) ||
    !Number.isInteger(gapCandles) ||
    candleCount < 1 ||
    trainCandles < 2 ||
    testCandles < 1 ||
    stepCandles < testCandles ||
    gapCandles < 0
  ) {
    return null;
  }

  const firstFoldCandles = trainCandles + gapCandles + testCandles;

  if (firstFoldCandles > candleCount) {
    return 0;
  }

  return Math.floor((candleCount - firstFoldCandles) / stepCandles) + 1;
}
