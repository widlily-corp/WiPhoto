const GPURenderer = (() => {
  let device = null;
  let pipeline = null;
  let canvasContext = null;
  let adjustmentsBuffer = null;
  let bindGroupLayout = null;
  
  const SHADER_CODE = `
    struct Adjustments {
      exposure: f32,
      contrast: f32,
      temperature: f32,
      saturation: f32,
      highlights: f32,
      shadows: f32,
      padding1: f32,
      padding2: f32,
    };

    @group(0) @binding(0) var input_tex: texture_2d<f32>;
    @group(0) @binding(1) var output_tex: texture_storage_2d<rgba8unorm, write>;
    @group(0) @binding(2) var<uniform> params: Adjustments;

    fn luminance(color: vec3<f32>) -> f32 {
      return dot(color, vec3<f32>(0.299, 0.587, 0.114));
    }

    @compute @workgroup_size(16, 16)
    fn main(@builtin(global_invocation_id) global_id: vec3<u32>) {
      let dimensions = textureDimensions(input_tex);
      let coord = vec2<u32>(global_id.xy);
      
      if (coord.x >= dimensions.x || coord.y >= dimensions.y) {
        return;
      }

      let in_color = textureLoad(input_tex, coord, 0).rgb;
      var color = in_color;

      // Exposure (multiply RGB by 2^exposure)
      color = color * pow(2.0, params.exposure);

      // Contrast (S-curve around midpoint 0.5)
      color = (color - 0.5) * max(params.contrast + 1.0, 0.0) + 0.5;

      // Temperature (shift R/B channels)
      // temperature: >0 warmer (more R, less B), <0 cooler (more B, less R)
      color.r = color.r + params.temperature * 0.1;
      color.b = color.b - params.temperature * 0.1;

      // Saturation (interpolate toward luminance)
      let lum = luminance(color);
      color = mix(vec3<f32>(lum), color, params.saturation + 1.0);

      // Highlights / Shadows (selective tonal adjustments)
      // Simple approximation:
      // if lum is high, adjust by highlights
      // if lum is low, adjust by shadows
      let shadow_mask = 1.0 - smoothstep(0.0, 0.5, lum);
      let highlight_mask = smoothstep(0.5, 1.0, lum);
      
      color = color + (shadow_mask * params.shadows * 0.5) + (highlight_mask * params.highlights * 0.5);

      // Clamp output
      color = clamp(color, vec3<f32>(0.0), vec3<f32>(1.0));

      textureStore(output_tex, coord, vec4<f32>(color, 1.0));
    }
  `;

  function isAvailable() {
    return typeof navigator !== 'undefined' && !!navigator.gpu;
  }

  async function init(canvas) {
    if (!isAvailable()) return false;

    try {
      const adapter = await navigator.gpu.requestAdapter();
      if (!adapter) return false;

      device = await adapter.requestDevice();

      canvasContext = canvas.getContext('webgpu');
      const canvasFormat = navigator.gpu.getPreferredCanvasFormat();
      canvasContext.configure({
        device,
        format: canvasFormat,
        alphaMode: 'premultiplied',
      });

      const shaderModule = device.createShaderModule({
        code: SHADER_CODE
      });

      bindGroupLayout = device.createBindGroupLayout({
        entries: [
          {
            binding: 0,
            visibility: GPUShaderStage.COMPUTE,
            texture: {
              sampleType: 'unfilterable-float',
              viewDimension: '2d',
              multisampled: false,
            },
          },
          {
            binding: 1,
            visibility: GPUShaderStage.COMPUTE,
            storageTexture: {
              access: 'write-only',
              format: 'rgba8unorm',
              viewDimension: '2d',
            },
          },
          {
            binding: 2,
            visibility: GPUShaderStage.COMPUTE,
            buffer: {
              type: 'uniform',
            },
          },
        ],
      });

      pipeline = device.createComputePipeline({
        layout: device.createPipelineLayout({
          bindGroupLayouts: [bindGroupLayout],
        }),
        compute: {
          module: shaderModule,
          entryPoint: 'main',
        },
      });

      // 6 f32 values + 2 padding = 8 * 4 bytes = 32 bytes
      adjustmentsBuffer = device.createBuffer({
        size: 32,
        usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
      });

      return true;
    } catch (e) {
      console.error('Failed to initialize WebGPU renderer', e);
      return false;
    }
  }

  async function render(imageBitmap, adjustments) {
    if (!device || !pipeline) {
      throw new Error('GPURenderer not initialized');
    }

    const { width, height } = imageBitmap;
    
    // Ensure canvas dimensions match image
    if (canvasContext.canvas.width !== width || canvasContext.canvas.height !== height) {
      canvasContext.canvas.width = width;
      canvasContext.canvas.height = height;
    }

    // 1. Upload image to texture
    const inputTexture = device.createTexture({
      size: [width, height, 1],
      format: 'rgba8unorm',
      usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST | GPUTextureUsage.RENDER_ATTACHMENT,
    });
    
    device.queue.copyExternalImageToTexture(
      { source: imageBitmap },
      { texture: inputTexture },
      [width, height]
    );

    // 2. Create output texture (rendered directly to canvas via compute shader if possible, 
    // or we render to a storage texture and copy to canvas. Wait, canvas texture doesn't support storage usage often.
    // So we use an intermediate texture and then copy)
    const outputTexture = device.createTexture({
      size: [width, height, 1],
      format: 'rgba8unorm',
      usage: GPUTextureUsage.STORAGE_BINDING | GPUTextureUsage.COPY_SRC,
    });

    // 3. Update uniforms
    const uniforms = new Float32Array([
      adjustments.exposure || 0,
      adjustments.contrast || 0,
      adjustments.temperature || 0,
      adjustments.saturation || 0,
      adjustments.highlights || 0,
      adjustments.shadows || 0,
      0, // padding
      0, // padding
    ]);
    device.queue.writeBuffer(adjustmentsBuffer, 0, uniforms);

    // 4. Bind group
    const bindGroup = device.createBindGroup({
      layout: bindGroupLayout,
      entries: [
        {
          binding: 0,
          resource: inputTexture.createView(),
        },
        {
          binding: 1,
          resource: outputTexture.createView(),
        },
        {
          binding: 2,
          resource: {
            buffer: adjustmentsBuffer,
          },
        },
      ],
    });

    // 5. Dispatch compute pass
    const commandEncoder = device.createCommandEncoder();
    const computePass = commandEncoder.beginComputePass();
    computePass.setPipeline(pipeline);
    computeGroupCountX = Math.ceil(width / 16);
    computeGroupCountY = Math.ceil(height / 16);
    computePass.setBindGroup(0, bindGroup);
    computePass.dispatchWorkgroups(computeGroupCountX, computeGroupCountY);
    computePass.end();

    // 6. Copy intermediate to canvas
    const currentTexture = canvasContext.getCurrentTexture();
    commandEncoder.copyTextureToTexture(
      { texture: outputTexture },
      { texture: currentTexture },
      [width, height, 1]
    );

    device.queue.submit([commandEncoder.finish()]);

    // Clean up
    inputTexture.destroy();
    outputTexture.destroy();
  }

  return {
    isAvailable,
    init,
    render,
  };
})();

if (typeof window !== 'undefined') {
  window.GPURenderer = GPURenderer;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = GPURenderer;
}
