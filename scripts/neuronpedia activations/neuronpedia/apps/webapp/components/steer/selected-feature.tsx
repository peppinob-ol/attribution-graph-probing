import { useGlobalContext } from '@/components/provider/global-provider';
import { STEER_STRENGTH_MAX, STEER_STRENGTH_MIN, SteerFeature } from '@/lib/utils/steer';
import { NeuronWithPartialRelations } from '@/prisma/generated/zod';
import * as Slider from '@radix-ui/react-slider';
import { ChevronsDown, ChevronsUp, X } from 'lucide-react';

export default function SteerSelectedFeature({
  feature,
  setFeatureStrength,
  selectedFeatures,
  setSelectedFeatures,
  findExplanationFromPresets,
}: {
  feature: SteerFeature;
  setFeatureStrength: (feature: SteerFeature, strength: number) => void;
  selectedFeatures: SteerFeature[];
  setSelectedFeatures: (features: SteerFeature[]) => void;
  findExplanationFromPresets: (modelId: string, layer: string, index: number) => string | undefined;
}) {
  const { setFeatureModalFeature, setFeatureModalOpen } = useGlobalContext();

  function deselectFeature(featureToDeselect: SteerFeature) {
    setSelectedFeatures(
      selectedFeatures.filter(
        (f) =>
          f.modelId !== featureToDeselect.modelId ||
          f.layer !== featureToDeselect.layer ||
          f.index !== featureToDeselect.index,
      ),
    );
  }

  function findSelectedFeature(selectedFeatureModelId: string, layer: string, index: number) {
    return selectedFeatures.find((f) => f.modelId === selectedFeatureModelId && f.layer === layer && f.index === index);
  }

  return (
    <div
      key={feature.modelId + feature.layer + feature.index}
      className="relative flex w-full flex-row items-center gap-x-0 self-center px-2 py-2.5"
    >
      <div className="flex flex-1 flex-col">
        <div className="mb-0.5 flex w-full flex-row items-center justify-center text-center text-[11px] font-bold leading-snug text-slate-600">
          <div className="mr-1.5 select-none rounded bg-slate-200 px-1.5 py-1 text-[8px] font-normal leading-none text-slate-600">
            {!feature.hasVector ? 'Feature' : 'Vector'}
          </div>
          {findExplanationFromPresets(feature.modelId, feature.layer, feature.index) || feature.explanation || (
            <span className="text-slate-400">No Explanation Available</span>
          )}
        </div>
        <div className="mt-0.5 flex w-full flex-row items-center gap-x-0.5 px-3 text-sky-700">
          <input
            type="number"
            value={findSelectedFeature(feature.modelId, feature.layer, feature.index)?.strength || 0}
            onChange={(e) => {
              const value = parseFloat(e.target.value);
              if (!Number.isNaN(value)) {
                const clampedValue = Math.min(Math.max(value, STEER_STRENGTH_MIN), STEER_STRENGTH_MAX);
                setFeatureStrength(feature, clampedValue);
              }
            }}
            className="mr-1 hidden h-6 w-12 rounded border border-sky-600 px-1 py-0.5 text-center text-[10px] font-medium leading-none text-sky-700 ring-0 focus:border-sky-700 sm:block"
          />
          <ChevronsDown className="mt-0 h-3 w-3" />
          <Slider.Root
            defaultValue={[feature.strength]}
            min={STEER_STRENGTH_MIN}
            max={STEER_STRENGTH_MAX}
            step={0.25}
            value={[findSelectedFeature(feature.modelId, feature.layer, feature.index)?.strength || 0]}
            onValueChange={(value) => {
              setFeatureStrength(feature, value[0]);
            }}
            className="group relative flex h-5 w-full cursor-pointer items-center"
          >
            <Slider.Track className="relative h-[8px] grow rounded-full border border-sky-600 bg-white group-hover:bg-sky-50">
              <Slider.Range className="absolute h-full rounded-full bg-sky-600 group-hover:bg-sky-700" />
              <div className="mx-auto mt-[7px] h-[8px] w-[1px] bg-sky-600" />
            </Slider.Track>
            <Slider.Thumb className="flex h-5 w-10 items-center justify-center rounded-full border border-sky-700 bg-white text-[10px] font-medium text-sky-700 shadow group-hover:bg-sky-100">
              {findSelectedFeature(feature.modelId, feature.layer, feature.index)?.strength.toFixed(2) || '0'}
            </Slider.Thumb>
          </Slider.Root>
          <ChevronsUp className="mt-0 h-3 w-3" />
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            e.preventDefault();
            setFeatureModalFeature({
              modelId: feature.modelId,
              layer: feature.layer,
              index: feature.index.toString(),
            } as NeuronWithPartialRelations);
            setFeatureModalOpen(true);
          }}
          className="mt-1 flex flex-row items-center justify-center gap-x-1.5 whitespace-pre rounded px-2 py-0.5 font-mono text-[9px] font-medium uppercase text-slate-500 hover:bg-sky-300 hover:text-sky-700"
        >
          {feature.layer}:{feature.index}
        </button>
      </div>
      <div className="flex flex-col gap-y-0.5">
        <button
          type="button"
          onClick={() => {
            deselectFeature(feature);
          }}
          className="flex flex-col items-center justify-center gap-y-0.5 rounded px-1.5 py-0.5 text-[9px] font-normal uppercase text-red-500 hover:bg-red-300 hover:text-red-700"
        >
          <X className="h-3 w-3" />
          Remove
        </button>
      </div>
    </div>
  );
}
