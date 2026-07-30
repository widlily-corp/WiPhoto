const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// Load utils.js content
const utilsPath = path.join(__dirname, 'utils.js');
const utilsCode = fs.readFileSync(utilsPath, 'utf8');

// Setup mock window/document environment
const context = {
  window: {}
};
context.self = context.window;

// Execute utils.js inside VM context
vm.runInNewContext(utilsCode, context);

const Utils = context.window.Utils;

describe('Utils Functions tests (AAA Pattern via VM Context)', () => {
  describe('Utils.formatSize', () => {
    it('should format bytes to human-readable size', () => {
      // Arrange
      const bytesZero = 0;
      const bytesKb = 1024;
      const bytesMb = 1024 * 1024 * 5.5;

      // Act
      const formattedZero = Utils.formatSize(bytesZero);
      const formattedKb = Utils.formatSize(bytesKb);
      const formattedMb = Utils.formatSize(bytesMb);

      // Assert
      assert.strictEqual(formattedZero, '0 B');
      assert.strictEqual(formattedKb, '1.0 KB');
      assert.strictEqual(formattedMb, '5.5 MB');
    });
  });

  describe('Utils.starsHtml', () => {
    it('should return filled and empty stars matching rating', () => {
      // Arrange
      const rating = 3;

      // Act
      const stars = Utils.starsHtml(rating);

      // Assert
      assert.strictEqual(stars, '★★★☆☆');
    });
  });

  describe('Utils.getExtension', () => {
    it('should extract lowercase extension from path', () => {
      // Arrange
      const path1 = 'C:/photos/my_photo.ARW';
      const path2 = '/usr/bin/image.jpeg';
      const path3 = 'no_extension';
      const path4 = 'C:/photos.holiday/my_photo';
      const path5 = 'C:/photos.holiday/my_photo.png';

      // Act
      const ext1 = Utils.getExtension(path1);
      const ext2 = Utils.getExtension(path2);
      const ext3 = Utils.getExtension(path3);
      const ext4 = Utils.getExtension(path4);
      const ext5 = Utils.getExtension(path5);
      const ext6 = Utils.getExtension('.gitignore');
      const ext7 = Utils.getExtension('archive.tar.gz');

      // Assert
      assert.strictEqual(ext1, 'arw');
      assert.strictEqual(ext2, 'jpeg');
      assert.strictEqual(ext3, '');
      assert.strictEqual(ext4, '');
      assert.strictEqual(ext5, 'png');
      assert.strictEqual(ext6, '');
      assert.strictEqual(ext7, 'gz');
    });
  });

  describe('Utils.getFilename', () => {
    it('should parse filename from Windows and POSIX paths', () => {
      // Arrange
      const winPath = 'C:\\Users\\Widlily\\Pictures\\img.png';
      const posixPath = '/home/user/pictures/img_raw.dng';

      // Act
      const winFile = Utils.getFilename(winPath);
      const posixFile = Utils.getFilename(posixPath);
      const winTrailing = Utils.getFilename('C:\\path\\to\\dir\\');
      const posixTrailing = Utils.getFilename('/home/user/dir/');

      // Assert
      assert.strictEqual(winFile, 'img.png');
      assert.strictEqual(posixFile, 'img_raw.dng');
      assert.strictEqual(winTrailing, 'dir');
      assert.strictEqual(posixTrailing, 'dir');
    });
  });

  describe('Utils.assetUrl', () => {
    it('should convert local file paths to zero-copy asset protocol URLs', () => {
      // Arrange
      const winPath = 'C:\\Users\\Widlily\\Pictures\\image.jpg';
      const posixPath = '/home/user/pictures/image.png';
      const existingAsset = 'asset://localhost/C%3A/Users/test.jpg';

      // Act
      const assetWin = Utils.assetUrl(winPath);
      const assetPosix = Utils.assetUrl(posixPath);
      const assetPassthrough = Utils.assetUrl(existingAsset);

      // Assert
      assert.strictEqual(assetWin, 'asset://localhost/C%3A/Users/Widlily/Pictures/image.jpg');
      assert.strictEqual(assetPosix, 'asset://localhost/home/user/pictures/image.png');
      assert.strictEqual(assetPassthrough, existingAsset);
    });

    it('should handle base64Src correctly with file paths and base64 strings', () => {
      // Arrange
      const filePath = 'C:\\photos\\img.jpg';
      const b64Data = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';

      // Act
      const pathResult = Utils.base64Src(filePath);
      const b64Result = Utils.base64Src(b64Data);

      // Assert
      assert.strictEqual(pathResult, 'asset://localhost/C%3A/photos/img.jpg');
      assert.strictEqual(b64Result, `data:image/jpeg;base64,${b64Data}`);
    });
  });
});
